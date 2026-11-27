"""Scheduled messaging tools for ZulipChat MCP v0.4.0.

Clean implementation of Zulip's scheduled message API endpoints.
Direct mapping to API without unnecessary complexity.
"""

import asyncio
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import Field

from ..config import get_client
from ..core.errors import api_error, internal_error, tool_error
from .params import MAX_CONTENT_CHARS, MessageId

MessageType = Annotated[
    Literal["stream", "private", "channel", "direct"],
    Field(description="channel (alias stream) or direct (alias private)."),
]
IdList = Annotated[list[int], Field(min_length=1, max_length=100)]
Recipients = Annotated[
    int | IdList,
    Field(description="Channel ID for a channel message; user IDs for a DM."),
]
DeliveryTime = Annotated[
    int,
    Field(gt=0, description="When Zulip sends it, as a UNIX timestamp in seconds."),
]
ScheduledId = Annotated[
    int,
    Field(gt=0, description="ID from get_scheduled_messages."),
]


async def get_scheduled_messages() -> dict[str, Any]:
    """Get all scheduled messages for the current user."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "scheduled_messages", method="GET", request={}
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_messages": result.get("scheduled_messages", []),
                "count": len(result.get("scheduled_messages", [])),
            }
        else:
            return api_error(result, "Failed to get scheduled messages")

    except Exception as e:
        return internal_error(e)


async def create_scheduled_message(
    type: MessageType,
    to: Recipients,
    content: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_CONTENT_CHARS,
            description="Message text in Zulip Markdown.",
        ),
    ],
    scheduled_delivery_timestamp: DeliveryTime,
    topic: Annotated[
        str | None,
        Field(max_length=60, description="Topic; required for channel messages."),
    ] = None,
    read_by_sender: Annotated[
        bool, Field(description="Mark the message read for you when it is sent.")
    ] = True,
) -> dict[str, Any]:
    """Create a scheduled message using Zulip's native API."""
    client = get_client()

    try:
        # Validate required parameters
        if type in ["stream", "channel"] and not topic:
            return tool_error("Topic required for stream/channel messages")

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

        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "scheduled_messages", method="POST", request=request_data
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_message_id": result.get("scheduled_message_id"),
                "scheduled_at": _iso(scheduled_delivery_timestamp),
            }
        else:
            return api_error(result, "Failed to create scheduled message")

    except Exception as e:
        return internal_error(e)


async def update_scheduled_message(
    scheduled_message_id: ScheduledId,
    type: Annotated[
        Literal["stream", "private", "channel", "direct"] | None,
        Field(description="New message type; give to with it."),
    ] = None,
    to: Annotated[
        int | IdList | None,
        Field(description="New channel ID, or new DM user IDs."),
    ] = None,
    content: Annotated[
        str | None,
        Field(
            max_length=MAX_CONTENT_CHARS,
            description="New text; replaces the old text entirely.",
        ),
    ] = None,
    topic: Annotated[str | None, Field(max_length=60, description="New topic.")] = None,
    scheduled_delivery_timestamp: Annotated[
        int | None,
        Field(gt=0, description="New send time as a UNIX timestamp in seconds."),
    ] = None,
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
            return tool_error("Must provide at least one field to update")

        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"scheduled_messages/{scheduled_message_id}",
                method="PATCH",
                request=request_data,
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_message_id": scheduled_message_id,
                "updated_fields": list(request_data.keys()),
                "new_delivery_time": _iso(scheduled_delivery_timestamp),
            }
        else:
            return api_error(
                result,
                "Failed to update scheduled message",
                recovery_tool="get_scheduled_messages",
            )

    except Exception as e:
        return internal_error(e)


async def delete_scheduled_message(
    scheduled_message_id: ScheduledId,
) -> dict[str, Any]:
    """Delete (cancel) a scheduled message."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"scheduled_messages/{scheduled_message_id}",
                method="DELETE",
                request={},
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "scheduled_message_id": scheduled_message_id,
                "action": "deleted",
            }
        else:
            return api_error(
                result,
                "Failed to delete scheduled message",
                recovery_tool="get_scheduled_messages",
            )

    except Exception as e:
        return internal_error(e)


def _timestamp(value: datetime | str) -> int:
    # Python 3.10 fromisoformat rejects a trailing Z.
    when = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return int(when.timestamp())


def _iso(timestamp: Any) -> str | None:
    if not isinstance(timestamp, (int, float)):
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


Reminder = Annotated[int, Field(gt=0, description="Reminder ID from get_reminders.")]


async def get_reminders() -> dict[str, Any]:
    """Your pending message reminders (FL 381+)."""
    client = get_client()
    try:
        result = await asyncio.to_thread(
            client.client.call_endpoint, "reminders", method="GET", request={}
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to list reminders")
        reminders = [
            {
                "reminder_id": r.get("reminder_id"),
                "message_id": r.get("reminder_target_message_id"),
                "deliver_at": _iso(r.get("scheduled_delivery_timestamp")),
                "failed": r.get("failed", False),
            }
            for r in result.get("reminders", [])
        ]
        return {"status": "success", "count": len(reminders), "reminders": reminders}
    except Exception as e:
        return internal_error(e)


async def create_reminder(
    message_id: MessageId,
    deliver_at: Annotated[
        datetime | Annotated[str, Field(max_length=64)],
        Field(
            description="When to be reminded, ISO 8601; a time without an offset "
            "is UTC."
        ),
    ],
    note: Annotated[
        str | None,
        Field(max_length=1000, description="Text shown with the reminder (FL 415+)."),
    ] = None,
) -> dict[str, Any]:
    """Schedule a private reminder about a message (FL 381+)."""
    client = get_client()
    try:
        request: dict[str, Any] = {
            "message_id": message_id,
            "scheduled_delivery_timestamp": _timestamp(deliver_at),
        }
        if note:
            request["note"] = note
        result = await asyncio.to_thread(
            client.client.call_endpoint, "reminders", method="POST", request=request
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to create reminder")
        return {
            "status": "success",
            "reminder_id": result.get("reminder_id"),
            "deliver_at": _iso(request["scheduled_delivery_timestamp"]),
        }
    except ValueError as e:
        return tool_error(f"deliver_at must be ISO 8601 ({e})")
    except Exception as e:
        return internal_error(e)


async def delete_reminder(reminder_id: Reminder) -> dict[str, Any]:
    """Cancel one of your reminders (FL 399+)."""
    client = get_client()
    try:
        result = await asyncio.to_thread(
            client.client.call_endpoint,
            f"reminders/{reminder_id}",
            method="DELETE",
            request={},
        )
        if result.get("result") != "success":
            return api_error(
                result, "Failed to delete reminder", recovery_tool="get_reminders"
            )
        return {"status": "success", "reminder_id": reminder_id, "deleted": True}
    except Exception as e:
        return internal_error(e)
