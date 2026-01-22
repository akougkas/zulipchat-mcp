"""Scheduled messaging tools for ZulipChat MCP v0.4.0.

Clean implementation of Zulip's scheduled message API endpoints.
Direct mapping to API without unnecessary complexity.
"""

from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import get_client


async def get_scheduled_messages() -> dict[str, Any]:
    """Get all scheduled messages for the current user."""
    client = get_client()

    try:
        result = client.client.call_endpoint(
            "scheduled_messages", method="GET", request={}
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_messages": result.get("scheduled_messages", []),
                "count": len(result.get("scheduled_messages", [])),
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to get scheduled messages"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def create_scheduled_message(
    type: Literal["stream", "private", "channel", "direct"],
    to: int | list[int],  # Channel ID or list of user IDs
    content: str,
    scheduled_delivery_timestamp: int,
    topic: str | None = None,
    read_by_sender: bool = True,
) -> dict[str, Any]:
    """Create a scheduled message using Zulip's native API."""
    client = get_client()

    try:
        # Validate required parameters
        if type in ["stream", "channel"] and not topic:
            return {
                "status": "error",
                "error": "Topic required for stream/channel messages",
            }

        # Prepare request data
        request_data = {
            "type": type,
            "to": to,
            "content": content,
            "scheduled_delivery_timestamp": scheduled_delivery_timestamp,
            "read_by_sender": read_by_sender,
        }

        if topic:
            request_data["topic"] = topic

        result = client.client.call_endpoint(
            "scheduled_messages", method="POST", request=request_data
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_message_id": result.get("scheduled_message_id"),
                "scheduled_at": datetime.fromtimestamp(
                    scheduled_delivery_timestamp
                ).isoformat(),
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to create scheduled message"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def update_scheduled_message(
    scheduled_message_id: int,
    type: Literal["stream", "private", "channel", "direct"] | None = None,
    to: int | list[int] | None = None,
    content: str | None = None,
    topic: str | None = None,
    scheduled_delivery_timestamp: int | None = None,
) -> dict[str, Any]:
    """Update a scheduled message's attributes."""
    client = get_client()

    try:
        # Build update data from provided parameters
        request_data: dict[str, Any] = {}
        if type is not None:
            request_data["type"] = type
        if to is not None:
            request_data["to"] = to
        if content is not None:
            request_data["content"] = content
        if topic is not None:
            request_data["topic"] = topic
        if scheduled_delivery_timestamp is not None:
            request_data["scheduled_delivery_timestamp"] = scheduled_delivery_timestamp

        if not request_data:
            return {
                "status": "error",
                "error": "Must provide at least one field to update",
            }

        result = client.client.call_endpoint(
            f"scheduled_messages/{scheduled_message_id}",
            method="PATCH",
            request=request_data,
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_message_id": scheduled_message_id,
                "updated_fields": list(request_data.keys()),
                "new_delivery_time": (
                    datetime.fromtimestamp(scheduled_delivery_timestamp).isoformat()
                    if scheduled_delivery_timestamp
                    else None
                ),
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to update scheduled message"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def delete_scheduled_message(scheduled_message_id: int) -> dict[str, Any]:
    """Delete (cancel) a scheduled message."""
    client = get_client()

    try:
        result = client.client.call_endpoint(
            f"scheduled_messages/{scheduled_message_id}", method="DELETE", request={}
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_message_id": scheduled_message_id,
                "action": "deleted",
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to delete scheduled message"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_schedule_messaging_tools(mcp: FastMCP) -> None:
    """Register scheduled messaging tools with the MCP server."""
    mcp.tool(
        name="get_scheduled_messages",
        description="Get all scheduled messages for current user",
    )(get_scheduled_messages)
    mcp.tool(
        name="create_scheduled_message",
        description="Create a scheduled message using Zulip's native API",
    )(create_scheduled_message)
    mcp.tool(
        name="update_scheduled_message",
        description="Update a scheduled message's attributes",
    )(update_scheduled_message)
    mcp.tool(
        name="delete_scheduled_message",
        description="Delete (cancel) a scheduled message",
    )(delete_scheduled_message)
