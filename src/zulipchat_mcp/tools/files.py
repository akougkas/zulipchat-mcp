"""File tools: upload, list, download, share and delete Zulip attachments.

Local paths are confined to the file root (--file-root, ZULIPCHAT_FILE_ROOT, or
the server's working directory) and to stdio; every transfer is capped at 25 MiB.
"""

import asyncio
import hashlib
import mimetypes
import os
import stat
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from datetime import datetime, timezone
from typing import Annotated, Any
from urllib.parse import unquote, urlparse, urlunparse

from pydantic import Field

from ..config import get_client
from ..core.errors import api_error, internal_error, tool_error
from ..core.security import (
    PathOutsideRoot,
    contained_path,
    file_root,
    is_unsafe_mode,
    local_access_allowed,
)
from .params import Cursor, Topic, page_size

MAX_FILE_SIZE = 25 * 1024 * 1024
FILE_TOO_LARGE = "File too large (max 25 MiB)"

FileId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=2000,
        description="A /user_uploads/... path or a full URL on this Zulip site, "
        "as returned by upload_file or get_files.",
    ),
]
ChannelName = Annotated[
    str, Field(min_length=1, max_length=60, description="Channel name.")
]


def _path_refused(error: PathOutsideRoot) -> dict[str, Any]:
    return tool_error(
        str(error),
        "PATH_OUTSIDE_ROOT",
        hint=f"Use a path inside {file_root()}, or start the server with "
        "--file-root.",
    )


def _read_local_file(path: str) -> bytes:
    """Read a regular file inside the file root, refusing more than 25 MiB."""
    resolved = contained_path(path)
    fd = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"{path} is not a regular file")
        if info.st_size > MAX_FILE_SIZE:
            raise ValueError(FILE_TOO_LARGE)
        return handle.read(MAX_FILE_SIZE + 1)


def _write_new_local_file(path: str, content: bytes) -> str:
    """Create path inside the file root; never replaces an existing entry."""
    resolved = contained_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(resolved, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
    return str(resolved)


def _validate_download_url(client: Any, url: str) -> None:
    """Only send Zulip credentials to attachment paths on the configured origin."""
    expected = urlparse(_resolve_file_url(client, "/user_uploads/"))
    target = urlparse(url)

    def origin(parsed: Any) -> tuple[str, str | None, int | None]:
        return (
            parsed.scheme,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
        )

    if (
        target.scheme not in {"http", "https"}
        or target.username is not None
        or target.password is not None
        or origin(target) != origin(expected)
    ):
        raise ValueError("Authenticated downloads must use the configured Zulip origin")
    path = unquote(target.path)
    if (
        not path.startswith(expected.path)
        or any(part in {".", ".."} for part in path.split("/"))
        or "\\" in path
        or any(ord(char) < 32 for char in path)
        or "%" in path
    ):
        raise ValueError("Downloads must use a valid Zulip /user_uploads/ path")


def _coerce_nonempty_str(value: Any) -> str | None:
    """Return value only when it is a non-empty string."""
    if isinstance(value, str) and value:
        return value
    return None


def _normalize_site_url(base_url: str) -> str:
    """Normalize a Zulip site URL to avoid API endpoint suffixes."""
    parsed = urlparse(base_url.strip())
    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[: -len("/api")]
    elif path.startswith("/api/v") and path[6:].isdigit():
        path = ""
    elif "/api/v" in path:
        path_prefix, _, version_suffix = path.rpartition("/api/v")
        if version_suffix.isdigit():
            path = path_prefix

    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

    return path or parsed.netloc or base_url.strip().rstrip("/")


def _normalize_upload_path(path: str) -> str:
    """Normalize a file identifier path to Zulip /user_uploads format."""
    normalized_path = path.strip()
    if normalized_path.startswith("/api/user_uploads/"):
        return normalized_path[len("/api") :]
    if normalized_path.startswith("api/user_uploads/"):
        return f"/{normalized_path[len('api/'):]}"
    if normalized_path.startswith("/user_uploads/"):
        return normalized_path
    if normalized_path.startswith("user_uploads/"):
        return f"/{normalized_path}"
    return f"/user_uploads/{normalized_path.lstrip('/')}"


def _resolve_file_url(client: Any, file_id: str) -> str:
    """Resolve file identifiers into absolute Zulip file URLs."""
    normalized_file_id = file_id.strip()
    if not normalized_file_id:
        raise ValueError("file_id cannot be empty")

    parsed = urlparse(normalized_file_id)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        absolute_path = parsed.path
        if absolute_path.startswith("/api/user_uploads/"):
            absolute_path = absolute_path[len("/api") :]
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                absolute_path,
                "",
                parsed.query,
                parsed.fragment,
            )
        )

    file_path = _normalize_upload_path(parsed.path or normalized_file_id)
    if parsed.query:
        file_path = f"{file_path}?{parsed.query}"
    if parsed.fragment:
        file_path = f"{file_path}#{parsed.fragment}"

    base_url = _coerce_nonempty_str(getattr(client, "base_url", None))
    if base_url:
        return f"{_normalize_site_url(base_url).rstrip('/')}{file_path}"

    sdk_client = getattr(client, "client", None)
    sdk_base_url = _coerce_nonempty_str(getattr(sdk_client, "base_url", None))
    if sdk_base_url:
        return f"{_normalize_site_url(sdk_base_url).rstrip('/')}{file_path}"

    raise ValueError("Unable to determine Zulip site URL for file operations")


def _resolve_download_credentials(client: Any) -> tuple[str, str]:
    """Resolve credentials used for authenticated file downloads."""
    sdk_client = getattr(client, "client", None)
    email = _coerce_nonempty_str(
        getattr(sdk_client, "email", None)
    ) or _coerce_nonempty_str(getattr(client, "current_email", None))
    api_key = _coerce_nonempty_str(getattr(sdk_client, "api_key", None))

    if email and api_key:
        return email, api_key

    config_manager = getattr(client, "config_manager", None)
    config = getattr(config_manager, "config", None)
    identity = _coerce_nonempty_str(getattr(client, "identity", None)) or "user"

    if config:
        preferred_email_key = "bot_email" if identity == "bot" else "email"
        preferred_api_key = "bot_api_key" if identity == "bot" else "api_key"

        # Only fill missing values from the selected identity's configuration;
        # resolved SDK credentials above take precedence.
        if not email:
            email = _coerce_nonempty_str(getattr(config, preferred_email_key, None))
        if not api_key:
            api_key = _coerce_nonempty_str(getattr(config, preferred_api_key, None))

    if not email or not api_key:
        raise ValueError("Missing Zulip credentials for authenticated file download")

    return email, api_key


def validate_file_security(file_content: bytes, filename: str) -> dict[str, Any]:
    """Validate file for security issues."""
    warnings = []
    file_size = len(file_content)

    # Check file size (25MB limit)
    if file_size > MAX_FILE_SIZE:
        return {"valid": False, "error": FILE_TOO_LARGE}

    # Basic MIME type detection
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Check for potentially dangerous file types
    dangerous_extensions = {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".pif",
        ".scr",
        ".vbs",
        ".ps1",
    }
    file_ext = os.path.splitext(filename)[1].lower()

    if file_ext in dangerous_extensions:
        warnings.append(f"Potentially dangerous file type: {file_ext}")

    # Calculate file hash for deduplication
    file_hash = hashlib.sha256(file_content).hexdigest()

    return {
        "valid": True,
        "warnings": warnings,
        "metadata": {
            "size": file_size,
            "mime_type": mime_type,
            "hash": file_hash,
            "extension": file_ext,
        },
    }


async def upload_file(
    file_content: Annotated[
        bytes | None,
        Field(
            description="File content as UTF-8 text. Use file_content_base64 for "
            "binary data."
        ),
    ] = None,
    file_path: Annotated[
        str | None,
        Field(
            max_length=4096,
            description="Local file to read (stdio only); must resolve inside the "
            "server's file root.",
        ),
    ] = None,
    filename: Annotated[
        str,
        Field(
            max_length=255,
            description="Name shown in Zulip; defaults to the file_path base "
            "name or upload.bin.",
        ),
    ] = "",
    mime_type: Annotated[
        str | None,
        Field(max_length=255, description="MIME type; guessed from filename."),
    ] = None,
    chunk_size: Annotated[
        int, Field(ge=1, description="Unused; accepted for compatibility.")
    ] = 1048576,
    stream: Annotated[
        str | None,
        Field(
            max_length=60,
            description="Also post the file link in this channel.",
        ),
    ] = None,
    topic: Annotated[
        str | None, Field(max_length=60, description="Topic for the post.")
    ] = None,
    message: Annotated[
        str | None,
        Field(max_length=10000, description="Text posted above the file link."),
    ] = None,
    file_content_base64: Annotated[
        str | None,
        Field(
            max_length=4 * ((MAX_FILE_SIZE + 2) // 3),
            description="Binary content as standard padded base64, at most "
            "25 MiB decoded.",
        ),
    ] = None,
) -> dict[str, Any]:
    """Upload one file source, optionally sharing it in a stream.

    Use file_content_base64 for binary data over MCP JSON: standard, padded base64
    with no whitespace, limited to 25 MiB decoded. An empty string uploads an empty
    file. file_content preserves UTF-8 text over JSON and bytes for Python callers;
    file_path is available only locally and only inside the file root. Supply
    exactly one of these sources.
    """
    source_count = sum(
        (file_content is not None, bool(file_path), file_content_base64 is not None)
    )
    if source_count != 1:
        return tool_error(
            "Exactly one of file_content, file_path, or file_content_base64 "
            "is required"
        )

    if file_path and not local_access_allowed():
        return tool_error(
            "Local file paths are disabled over HTTP; use file_content "
            "or file_content_base64",
            "NOT_AVAILABLE",
        )

    if file_content_base64 is not None:
        # Bound the encoded allocation before decoding; padding means the decoded
        # length must still be checked by validate_file_security below.
        if len(file_content_base64) > 4 * ((MAX_FILE_SIZE + 2) // 3):
            return tool_error(FILE_TOO_LARGE, "TOO_LARGE")
        try:
            file_content = b64decode(file_content_base64, validate=True)
        except (Base64Error, ValueError):
            return tool_error(
                "file_content_base64 must be valid standard padded base64"
            )
        if b64encode(file_content).decode("ascii") != file_content_base64:
            return tool_error(
                "file_content_base64 must be canonical standard padded base64"
            )

    try:
        if file_path and file_content is None:
            try:
                file_content = await asyncio.to_thread(_read_local_file, file_path)
            except PathOutsideRoot as error:
                return _path_refused(error)
            except (OSError, ValueError) as error:
                return tool_error(f"Failed to read file: {error}", "FILE_UNREADABLE")
            if not filename:
                filename = os.path.basename(file_path)

        if not filename:
            filename = "upload.bin"

        if file_content is None:
            return tool_error("No file content provided")

        validation = validate_file_security(file_content, filename)
        if not validation["valid"]:
            return tool_error(validation["error"], "TOO_LARGE")

        client = get_client()

        if not mime_type:
            mime_type = validation["metadata"]["mime_type"]

        upload_result = await asyncio.to_thread(
            client.upload_file, file_content, filename
        )

        if upload_result.get("result") != "success":
            return api_error(upload_result, "Upload failed")

        file_url = upload_result.get("uri", "")
        response: dict[str, Any] = {
            "status": "success",
            "file_url": file_url,
            "filename": filename,
            "file_size": validation["metadata"]["size"],
            "mime_type": mime_type,
            "hash": validation["metadata"]["hash"],
            "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if validation["warnings"]:
            response["warnings"] = validation["warnings"]

        if stream and file_url:
            share_content = message or f"📎 Uploaded file: **{filename}**"
            try:
                shared_file_url = await asyncio.to_thread(
                    _resolve_file_url, client, file_url
                )
            except ValueError:
                shared_file_url = file_url
            share_content += f"\n{shared_file_url}"

            size_mb = validation["metadata"]["size"] / (1024 * 1024)
            if size_mb >= 1:
                share_content += f"\n📊 Size: {size_mb:.1f} MB"
            else:
                size_kb = validation["metadata"]["size"] / 1024
                share_content += f"\n📊 Size: {size_kb:.1f} KB"

            share_result = await asyncio.to_thread(
                client.send_message, "stream", stream, share_content, topic
            )
            if share_result.get("result") == "success":
                response["shared_message_id"] = share_result.get("id")
                response["shared_in_stream"] = stream
                response["shared_in_topic"] = topic
            else:
                response["status"] = "partial"
                response["error"] = api_error(
                    share_result, "File uploaded but sharing failed"
                )["error"]

        return response

    except Exception as e:
        return internal_error(e)


async def get_files(
    limit: Annotated[int, page_size(500, "files")] = 50,
    cursor: Cursor = None,
) -> dict[str, Any]:
    """List the files you uploaded, newest first, one page at a time."""
    after: int | None = None
    if cursor is not None:
        try:
            after = int(cursor)
        except ValueError:
            return tool_error(
                "cursor must be the next_cursor of a previous get_files call",
                "INVALID_CURSOR",
            )
    client = get_client()
    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint("attachments", method="GET", request={})
        )
    except Exception as e:
        return internal_error(e)
    if result.get("result") != "success":
        return api_error(result, "Failed to list files")
    attachments = sorted(
        result.get("attachments", []), key=lambda a: a.get("id", 0), reverse=True
    )
    if after is not None:
        attachments = [a for a in attachments if a.get("id", 0) < after]
    page = attachments[:limit]
    response: dict[str, Any] = {
        "status": "success",
        "count": len(page),
        "total": len(result.get("attachments", [])),
    }
    if len(attachments) > len(page):
        response["next_cursor"] = str(page[-1].get("id"))
    if "upload_space_used" in result:
        response["upload_space_used"] = result["upload_space_used"]
    response["files"] = page
    return response


async def download_file(
    file_id: FileId,
    download_path: Annotated[
        str | None,
        Field(
            max_length=4096,
            description="Write the file here (stdio only). It must resolve inside "
            "the server's file root and must not exist yet. Omit to get only the "
            "download URL.",
        ),
    ] = None,
) -> dict[str, Any]:
    """Resolve a Zulip file's download URL, or save the file to a new local path."""
    client = get_client()
    try:
        download_url = await asyncio.to_thread(_resolve_file_url, client, file_id)
    except ValueError as e:
        return tool_error(str(e))

    if not download_path:
        return {
            "status": "success",
            "file_id": file_id,
            "download_url": download_url,
            "note": "Fetching the URL requires Zulip credentials; pass "
            "download_path to save the file instead.",
        }
    if not local_access_allowed():
        return tool_error(
            "Local file paths are disabled over HTTP; omit download_path",
            "NOT_AVAILABLE",
        )
    try:
        contained_path(download_path)
    except PathOutsideRoot as error:
        return _path_refused(error)
    if os.path.lexists(download_path):
        return tool_error(
            f"{download_path} already exists; download_file never overwrites",
            "ALREADY_EXISTS",
            hint="Choose a new file name.",
        )
    try:
        import httpx

        _validate_download_url(client, download_url)
        email, api_key = await asyncio.to_thread(_resolve_download_credentials, client)
        auth_bytes = b64encode(f"{email}:{api_key}".encode()).decode()
        headers = {"Authorization": f"Basic {auth_bytes}"}

        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as http:
            async with http.stream("GET", download_url, headers=headers) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    if len(content) + len(chunk) > MAX_FILE_SIZE:
                        raise ValueError(FILE_TOO_LARGE)
                    content.extend(chunk)

        written = await asyncio.to_thread(
            _write_new_local_file, download_path, bytes(content)
        )
    except PathOutsideRoot as error:
        return _path_refused(error)
    except FileExistsError:
        return tool_error(
            f"{download_path} already exists; download_file never overwrites",
            "ALREADY_EXISTS",
            hint="Choose a new file name.",
        )
    except Exception as e:
        return tool_error(f"Download failed: {e}", "DOWNLOAD_FAILED")
    return {
        "status": "success",
        "file_id": file_id,
        "download_path": written,
        "file_size": len(content),
    }


async def share_file(
    file_id: FileId,
    stream: ChannelName,
    topic: Annotated[Topic | None, Field(description="Topic for the post.")] = None,
) -> dict[str, Any]:
    """Post a link to an uploaded Zulip file in a channel topic."""
    client = get_client()
    try:
        file_url = await asyncio.to_thread(_resolve_file_url, client, file_id)
    except ValueError as e:
        return tool_error(str(e))
    try:
        result = await asyncio.to_thread(
            client.send_message, "stream", stream, f"📎 Shared file: {file_url}", topic
        )
    except Exception as e:
        return internal_error(e)
    if result.get("result") != "success":
        return api_error(result, "Failed to share file")
    return {
        "status": "success",
        "file_id": file_id,
        "shared_in_stream": stream,
        "shared_in_topic": topic,
        "message_id": result.get("id"),
    }


async def delete_file(
    attachment_id: Annotated[
        int, Field(ge=1, description="Attachment id from get_files.")
    ],
) -> dict[str, Any]:
    """Delete one of your uploaded files from Zulip (requires --unsafe)."""
    if not is_unsafe_mode():
        return tool_error(
            "File deletion requires the server's --unsafe mode", "POLICY_DENIED"
        )
    client = get_client()
    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"attachments/{attachment_id}", method="DELETE", request={}
            )
        )
    except Exception as e:
        return internal_error(e)
    if result.get("result") != "success":
        return api_error(result, "Failed to delete file", recovery_tool="get_files")
    return {"status": "success", "attachment_id": attachment_id, "deleted": True}
