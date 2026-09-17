"""Draft tools for ZulipChat MCP v0.7.1.

Clean implementation of Zulip's draft API endpoints.
Direct mapping to API without unnecessary complexity.
"""

import asyncio
import json
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import get_client
from .registration import register_tool
from .search import resolve_user_identifier

DraftRecipient = str | int


def _build_draft(
    type: Literal["stream", "private"],
    to: list[int],
    topic: str,
    content: str,
    timestamp: int | None,
) -> dict[str, Any]:
    """Build a draft object for Zulip's API."""
    draft: dict[str, Any] = {
        "type": type,
        "to": to,
        "topic": topic,
        "content": content,
    }
    if timestamp is not None:
        draft["timestamp"] = timestamp
    return draft


def _validate_draft(
    type: Literal["stream", "private"], to: list[int], topic: str
) -> str | None:
    """Validate addressing fields required by Zulip's drafts API."""
    if type == "stream" and not topic:
        return "Topic required for stream drafts"
    if type == "stream" and len(to) != 1:
        return "Stream drafts must specify exactly one channel"
    return None


async def _resolve_recipients(
    type: Literal["stream", "private"],
    to: DraftRecipient | list[DraftRecipient],
    client: Any,
) -> list[int]:
    """Resolve draft recipient names while preserving raw IDs."""
    recipients = to if isinstance(to, list) else [to]
    resolved: list[int] = []

    for recipient in recipients:
        if isinstance(recipient, int):
            resolved.append(recipient)
        elif type == "stream":
            result = await asyncio.to_thread(client.get_stream_id, recipient)
            stream_id = result.get("stream_id")
            if result.get("result") != "success" or not isinstance(stream_id, int):
                raise ValueError(result.get("msg", f"No stream matching '{recipient}'"))
            resolved.append(stream_id)
        else:
            user = await resolve_user_identifier(recipient, client)
            user_id = user.get("user_id")
            if not isinstance(user_id, int):
                raise ValueError(f"No user ID available for '{recipient}'")
            resolved.append(user_id)

    return resolved


async def get_drafts() -> dict[str, Any]:
    """Get all drafts for the current user."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint("drafts", method="GET", request={})
        )

        if result.get("result") == "success":
            drafts = result.get("drafts", [])
            return {
                "status": "success",
                "drafts": drafts,
                "count": len(drafts),
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to get drafts"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def create_draft(
    type: Literal["stream", "private"],
    to: DraftRecipient | list[DraftRecipient],
    content: str,
    topic: str = "",
    timestamp: int | None = None,
) -> dict[str, Any]:
    """Create a draft using Zulip's native API."""
    client = get_client()

    try:
        resolved_to = await _resolve_recipients(type, to, client)
        validation_error = _validate_draft(type, resolved_to, topic)
        if validation_error:
            return {"status": "error", "error": validation_error}

        draft = _build_draft(type, resolved_to, topic, content, timestamp)
        request_data = {"drafts": json.dumps([draft])}

        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "drafts", method="POST", request=request_data
            )
        )

        if result.get("result") == "success":
            draft_ids = result.get("ids", [])
            return {
                "status": "success",
                "draft_id": draft_ids[0] if draft_ids else None,
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to create draft"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def edit_draft(
    draft_id: int,
    type: Literal["stream", "private"],
    to: DraftRecipient | list[DraftRecipient],
    content: str,
    topic: str = "",
    timestamp: int | None = None,
) -> dict[str, Any]:
    """Edit a draft using Zulip's native API."""
    client = get_client()

    try:
        resolved_to = await _resolve_recipients(type, to, client)
        validation_error = _validate_draft(type, resolved_to, topic)
        if validation_error:
            return {"status": "error", "error": validation_error}

        draft = _build_draft(type, resolved_to, topic, content, timestamp)
        request_data = {"draft": json.dumps(draft)}

        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"drafts/{draft_id}", method="PATCH", request=request_data
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "draft_id": draft_id,
                "action": "edited",
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to edit draft"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def delete_draft(draft_id: int) -> dict[str, Any]:
    """Delete a draft."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"drafts/{draft_id}", method="DELETE", request={}
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "draft_id": draft_id,
                "action": "deleted",
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to delete draft"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_drafts_tools(mcp: FastMCP) -> None:
    """Register draft tools with the MCP server."""
    register_tool(
        mcp,
        get_drafts,
        name="get_drafts",
        description="Get all drafts for current user",
    )
    register_tool(
        mcp,
        create_draft,
        name="create_draft",
        description="Create a draft using Zulip's native API",
    )
    register_tool(
        mcp,
        edit_draft,
        name="edit_draft",
        description="Edit a draft's attributes",
    )
    register_tool(mcp, delete_draft, name="delete_draft", description="Delete a draft")
