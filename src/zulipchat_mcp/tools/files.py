"""File management tools for ZulipChat MCP v0.4.0.

Complete file operations including upload, management, sharing, and security validation.
All functionality from the complex v25 architecture preserved in minimal code.
"""

import hashlib
import mimetypes
import os
from base64 import b64encode
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

from fastmcp import FastMCP

from ..config import get_client


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
    email = _coerce_nonempty_str(getattr(sdk_client, "email", None)) or _coerce_nonempty_str(
        getattr(client, "current_email", None)
    )
    api_key = _coerce_nonempty_str(getattr(sdk_client, "api_key", None))

    config_manager = getattr(client, "config_manager", None)
    config = getattr(config_manager, "config", None)
    identity = _coerce_nonempty_str(getattr(client, "identity", None)) or "user"

    if config:
        preferred_email_key = "bot_email" if identity == "bot" else "email"
        preferred_api_key = "bot_api_key" if identity == "bot" else "api_key"

        # If identity is bot and bot credentials exist in config, prefer them
        # over what the SDK client might have loaded from a generic config file.
        if identity == "bot":
            config_bot_email = _coerce_nonempty_str(getattr(config, "bot_email", None))
            config_bot_api_key = _coerce_nonempty_str(getattr(config, "bot_api_key", None))
            if config_bot_email and config_bot_api_key:
                email = config_bot_email
                api_key = config_bot_api_key

        if not email:
            email = _coerce_nonempty_str(getattr(config, preferred_email_key, None))
        if not api_key:
            api_key = _coerce_nonempty_str(getattr(config, preferred_api_key, None))

        if not email:
            email = _coerce_nonempty_str(getattr(config, "email", None))
        if not api_key:
            api_key = _coerce_nonempty_str(getattr(config, "api_key", None))

    if not email or not api_key:
        raise ValueError("Missing Zulip credentials for authenticated file download")

    return email, api_key


def validate_file_security(file_content: bytes, filename: str) -> dict[str, Any]:
    """Validate file for security issues."""
    warnings = []
    file_size = len(file_content)

    # Check file size (25MB limit)
    if file_size > 25 * 1024 * 1024:
        return {"valid": False, "error": "File too large (max 25MB)"}

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
    file_content: bytes | None = None,
    file_path: str | None = None,
    filename: str = "",
    mime_type: str | None = None,
    chunk_size: int = 1048576,  # 1MB chunks
    stream: str | None = None,
    topic: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Upload files to Zulip with comprehensive capabilities and security validation."""
    if not file_content and not file_path:
        return {
            "status": "error",
            "error": "Either file_content or file_path is required",
        }

    client = get_client()

    try:
        # Read file if path provided
        if file_path and not file_content:
            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()
                if not filename:
                    filename = os.path.basename(file_path)
            except Exception as e:
                return {"status": "error", "error": f"Failed to read file: {str(e)}"}

        if not filename:
            filename = "upload.bin"

        if file_content is None:
            return {"status": "error", "error": "No file content provided"}

        # Security validation
        validation = validate_file_security(file_content, filename)
        if not validation["valid"]:
            return {"status": "error", "error": validation["error"]}

        # Auto-detect MIME type if not provided
        if not mime_type:
            mime_type = validation["metadata"]["mime_type"]

        # Upload file with progress tracking for large files
        upload_result = client.upload_file(file_content, filename)

        if upload_result.get("result") == "success":
            file_url = upload_result.get("uri", "")

            response = {
                "status": "success",
                "file_url": file_url,
                "filename": filename,
                "file_size": validation["metadata"]["size"],
                "mime_type": mime_type,
                "hash": validation["metadata"]["hash"],
                "upload_timestamp": datetime.now().isoformat(),
            }

            if validation["warnings"]:
                response["warnings"] = validation["warnings"]

            # Optionally share in stream
            if stream and file_url:
                share_content = message or f"📎 Uploaded file: **{filename}**"
                try:
                    shared_file_url = _resolve_file_url(client, file_url)
                except ValueError:
                    shared_file_url = file_url
                share_content += f"\n{shared_file_url}"

                # Add file metadata to share message
                size_mb = validation["metadata"]["size"] / (1024 * 1024)
                if size_mb >= 1:
                    share_content += f"\n📊 Size: {size_mb:.1f} MB"
                else:
                    size_kb = validation["metadata"]["size"] / 1024
                    share_content += f"\n📊 Size: {size_kb:.1f} KB"

                share_result = client.send_message(
                    "stream", stream, share_content, topic
                )
                if share_result.get("result") == "success":
                    response["shared_message_id"] = share_result.get("id")
                    response["shared_in_stream"] = stream
                    response["shared_in_topic"] = topic

            return response

        else:
            return {
                "status": "error",
                "error": upload_result.get("msg", "Upload failed"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def manage_files(
    operation: Literal[
        "list",
        "get",
        "delete",
        "share",
        "download",
        "generate_thumbnail",
        "get_permissions",
    ],
    file_id: str | None = None,
    filters: dict[str, Any] | None = None,
    download_path: str | None = None,
    share_in_stream: str | None = None,
    share_in_topic: str | None = None,
) -> dict[str, Any]:
    """Comprehensive file management operations with Zulip API limitations."""
    client = get_client()

    try:
        if operation == "list":
            # Use Zulip's attachments API (Feature level 2+)
            result = client.client.call_endpoint(
                "attachments", method="GET", request={}
            )
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "list",
                    "files": result.get("attachments", []),
                    "count": len(result.get("attachments", [])),
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to list files"),
                }

        elif operation == "delete":
            if not file_id:
                return {
                    "status": "error",
                    "error": "file_id (attachment ID) required for delete operation",
                }

            try:
                attachment_id = int(file_id)
            except ValueError:
                return {
                    "status": "error",
                    "error": "file_id must be a numeric attachment ID for deletion",
                }

            # Use Zulip's delete attachment API (Feature level 179+)
            result = client.client.call_endpoint(
                f"attachments/{attachment_id}", method="DELETE", request={}
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "delete",
                    "message": "File deleted successfully",
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to delete file"),
                }

        elif operation == "share":
            if not file_id:
                return {
                    "status": "error",
                    "error": "file_id required for share operation",
                }

            if not share_in_stream:
                return {
                    "status": "error",
                    "error": "share_in_stream required for share operation",
                }

            try:
                file_url = _resolve_file_url(client, file_id)
            except ValueError as e:
                return {"status": "error", "error": str(e)}

            share_content = f"📎 Shared file: {file_url}"

            result = client.send_message(
                "stream", share_in_stream, share_content, share_in_topic
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "share",
                    "file_id": file_id,
                    "shared_in_stream": share_in_stream,
                    "shared_in_topic": share_in_topic,
                    "message_id": result.get("id"),
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to share file"),
                }

        elif operation == "download":
            if not file_id:
                return {
                    "status": "error",
                    "error": "file_id required for download operation",
                }

            try:
                download_url = _resolve_file_url(client, file_id)
            except ValueError as e:
                return {"status": "error", "error": str(e)}

            if download_path:
                try:
                    import httpx

                    email, api_key = _resolve_download_credentials(client)
                    auth_bytes = b64encode(f"{email}:{api_key}".encode()).decode()
                    headers = {"Authorization": f"Basic {auth_bytes}"}

                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.get(download_url, headers=headers)
                        response.raise_for_status()

                        with open(download_path, "wb") as f:
                            f.write(response.content)

                    return {
                        "status": "success",
                        "operation": "download",
                        "file_id": file_id,
                        "download_path": download_path,
                        "file_size": len(response.content),
                    }

                except Exception as e:
                    return {"status": "error", "error": f"Download failed: {str(e)}"}
            else:
                return {
                    "status": "success",
                    "operation": "download",
                    "file_id": file_id,
                    "download_url": download_url,
                    "note": "Use the download_url to fetch the file content",
                }

        elif operation == "get_permissions":
            return {
                "status": "success",
                "operation": "get_permissions",
                "permissions": {
                    "note": "File permissions follow stream access rules in Zulip",
                    "public_files": "Accessible to all users in organization",
                    "stream_files": "Accessible to stream subscribers",
                    "private_files": "Accessible only to conversation participants",
                },
            }

        else:
            return {
                "status": "error",
                "error": f"Operation '{operation}' not implemented",
                "available_operations": [
                    "list",
                    "delete",
                    "share",
                    "download",
                    "get_permissions",
                ],
                "note": "Zulip API has limited file management capabilities",
            }

    except Exception as e:
        return {"status": "error", "error": str(e), "operation": operation}


def register_files_tools(mcp: FastMCP) -> None:
    """Register file tools with the MCP server."""
    mcp.tool(
        name="upload_file",
        description="Upload files with comprehensive security validation and sharing",
    )(upload_file)
    mcp.tool(
        name="manage_files",
        description="File management operations with Zulip API limitations",
    )(manage_files)
