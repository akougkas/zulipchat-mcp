"""Draft tools for ZulipChat MCP v0.7.1.

Clean implementation of Zulip's draft API endpoints.
Direct mapping to API without unnecessary complexity.
"""

import asyncio
import json
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from ..config import get_client
from ..core.errors import api_error, internal_error, tool_error
from .params import MAX_CONTENT_CHARS, Name
from .registration import register_tool
from .search import (
    AmbiguousUserError,
    UserNotFoundError,
    resolve_user_identifier,
)

DraftRecipient = Name | int
DraftType = Annotated[
    Literal["stream", "private"],
    Field(description="stream for a channel draft; private for a DM draft."),
]
DraftTo = Annotated[
    DraftRecipient | Annotated[list[DraftRecipient], Field(max_length=100)],
    Field(
        description="For stream: one channel name or ID. For private: user names, "
        "emails or IDs."
    ),
]
DraftContent = Annotated[
    str, Field(max_length=MAX_CONTENT_CHARS, description="Draft text in Markdown.")
]
DraftTopic = Annotated[
    str, Field(max_length=60, description="Topic; required for stream drafts.")
]
DraftTime = Annotated[
    int | None,
    Field(gt=0, description="Last-edited time as a UNIX timestamp; defaults to now."),
]
DraftId = Annotated[int, Field(gt=0, description="Draft ID from get_drafts.")]


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
                raise LookupError(
                    result.get("msg", f"No stream matching '{recipient}'")
                )
            resolved.append(stream_id)
        else:
            user = await resolve_user_identifier(recipient, client)
            user_id = user.get("user_id")
            if not isinstance(user_id, int):
                raise UserNotFoundError(recipient)
            resolved.append(user_id)

    return resolved


def _recipient_error(e: Exception) -> dict[str, Any]:
    if isinstance(e, LookupError):
        return tool_error(str(e), "NOT_FOUND", recovery_tool="get_streams")
    code = "AMBIGUOUS_USER" if isinstance(e, AmbiguousUserError) else "USER_NOT_FOUND"
    return tool_error(str(e), code, recovery_tool="resolve_user")


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
            return api_error(result, "Failed to get drafts")

    except Exception as e:
        return internal_error(e)


async def create_draft(
    type: DraftType,
    to: DraftTo,
    content: DraftContent,
    topic: DraftTopic = "",
    timestamp: DraftTime = None,
) -> dict[str, Any]:
    """Create a draft using Zulip's native API."""
    client = get_client()

    try:
        try:
            resolved_to = await _resolve_recipients(type, to, client)
        except (LookupError, AmbiguousUserError, UserNotFoundError) as e:
            return _recipient_error(e)
        validation_error = _validate_draft(type, resolved_to, topic)
        if validation_error:
            return tool_error(validation_error)

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
            return api_error(result, "Failed to create draft")

    except Exception as e:
        return internal_error(e)


async def edit_draft(
    draft_id: DraftId,
    type: DraftType,
    to: DraftTo,
    content: DraftContent,
    topic: DraftTopic = "",
    timestamp: DraftTime = None,
) -> dict[str, Any]:
    """Edit a draft using Zulip's native API."""
    client = get_client()

    try:
        try:
            resolved_to = await _resolve_recipients(type, to, client)
        except (LookupError, AmbiguousUserError, UserNotFoundError) as e:
            return _recipient_error(e)
        validation_error = _validate_draft(type, resolved_to, topic)
        if validation_error:
            return tool_error(validation_error)

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
            return api_error(result, "Failed to edit draft")

    except Exception as e:
        return internal_error(e)


async def delete_draft(draft_id: DraftId) -> dict[str, Any]:
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
            return api_error(result, "Failed to delete draft")

    except Exception as e:
        return internal_error(e)


def register_drafts_tools(mcp: FastMCP) -> None:
    """Register draft tools with the MCP server."""
    register_tool(
        mcp,
        get_drafts,
        name="get_drafts",
        description=(
            "List your saved Zulip drafts with their text, recipients and topic. "
            "Drafts are private to you; nothing here is sent. To send, use "
            "send_message."
        ),
        title="Get drafts",
    )
    register_tool(
        mcp,
        create_draft,
        name="create_draft",
        description=(
            "Save a new Zulip draft without sending it; returns draft_id. To "
            "send now use send_message; to send later use "
            "create_scheduled_message."
        ),
        title="Create draft",
    )
    register_tool(
        mcp,
        edit_draft,
        name="edit_draft",
        description=(
            "Replace a saved Zulip draft's recipients, topic and text; every "
            "field is overwritten, so pass the full new draft."
        ),
        title="Edit draft",
        destructive=True,
        idempotent=True,
    )
    register_tool(
        mcp,
        delete_draft,
        name="delete_draft",
        description=(
            "Delete one saved Zulip draft permanently. Does not affect sent or "
            "scheduled messages."
        ),
        title="Delete draft",
        destructive=True,
        idempotent=True,
    )
