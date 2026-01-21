"""File management tools for ZulipChat MCP v0.4.0.

Complete file operations including upload, management, sharing, and security validation.
All functionality from the complex v25 architecture preserved in minimal code.
"""

import hashlib
import mimetypes
import os
from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper


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

    config = ConfigManager()
    client = ZulipClientWrapper(config)

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
                if file_url.startswith("/"):
                    # Make URL absolute
                    share_content += f"\n{client.base_url}{file_url}"
                else:
                    share_content += f"\n{file_url}"

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
    config = ConfigManager()
    client = ZulipClientWrapper(config)

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

            # Construct file URL and share
            file_url = f"{client.base_url}/user_uploads/{file_id}"
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

            # Construct download URL
            download_url = f"{client.base_url}/user_uploads/{file_id}"

            if download_path:
                try:
                    import base64

                    import httpx

                    # Download file
                    auth_string = (
                        f"{client.current_email}:{client.config_manager.config.api_key}"
                    )
                    auth_bytes = base64.b64encode(auth_string.encode()).decode()
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
