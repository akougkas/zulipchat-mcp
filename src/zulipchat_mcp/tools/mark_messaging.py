"""Message marking tools for ZulipChat MCP v0.4.0.

Clean implementation of Zulip's message flag update API endpoints.
Uses modern "update personal message flags for narrow" instead of deprecated endpoints.
"""

import asyncio
from typing import Annotated, Any, Literal

from pydantic import Field

from ..config import bind_client, get_client
from ..core.errors import api_error, error_object, internal_error, tool_error
from ..utils.narrow_helpers import wire_narrow
from .params import MessageId, Name


def _criteria_narrow(
    stream_id: int | str | None = None,
    topic_name: str | None = None,
    sender_email: str | None = None,
) -> list[dict[str, Any]]:
    """Narrow from convenience filters; the channel operand takes an ID or a name."""
    narrow: list[dict[str, Any]] = []
    if stream_id:
        narrow.append({"operator": "channel", "operand": stream_id})
    if topic_name:
        narrow.append({"operator": "topic", "operand": topic_name})
    if sender_email:
        narrow.append({"operator": "sender", "operand": sender_email})
    return narrow


Narrow = Annotated[
    list[dict[str, Any]],
    Field(
        max_length=20,
        description='Zulip narrow terms, e.g. [{"operator": "channel", '
        '"operand": "general"}, {"operator": "topic", "operand": "deploys"}].',
    ),
]
Flag = Annotated[
    Literal["read", "starred"],
    Field(description="read marks read/unread; starred stars/unstars."),
]
Action = Annotated[
    Literal["add", "remove"],
    Field(description="add sets the flag (read, starred); remove clears it."),
]


async def update_message_flags_for_narrow(
    narrow: Narrow,
    op: Action,
    flag: Annotated[
        str,
        Field(
            min_length=1,
            max_length=30,
            description="Personal flag to change: read, starred or collapsed.",
        ),
    ],
    anchor: Annotated[
        int | Literal["first_unread", "oldest", "newest"],
        Field(description="Message ID or position the window is counted from."),
    ] = "newest",
    include_anchor: Annotated[
        bool, Field(description="Include the anchor message itself.")
    ] = True,
    num_before: Annotated[
        int,
        Field(ge=0, le=1000, description="Messages before the anchor (0-1000)."),
    ] = 50,
    num_after: Annotated[
        int,
        Field(ge=0, le=1000, description="Messages after the anchor (0-1000)."),
    ] = 50,
) -> dict[str, Any]:
    """Update personal message flags for messages matching a narrow (modern approach)."""
    client = get_client()

    try:
        request_data = {
            "narrow": wire_narrow(narrow, client.supports),
            "op": op,
            "flag": flag,
            "anchor": anchor,
            "include_anchor": include_anchor,
            "num_before": num_before,
            "num_after": num_after,
        }

        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "messages/flags/narrow", method="POST", request=request_data
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "operation": f"{op}_{flag}",
                "processed_count": result.get("processed_count", 0),
                "updated_count": result.get("updated_count", 0),
                "first_processed_id": result.get("first_processed_id"),
                "last_processed_id": result.get("last_processed_id"),
                "found_oldest": result.get("found_oldest", False),
                "found_newest": result.get("found_newest", False),
            }
        else:
            return api_error(result, "Failed to update message flags")

    except Exception as e:
        return internal_error(e)


async def _update_flag_pages(
    narrow: list[dict[str, Any]],
    op: Literal["add", "remove"],
    flag: Literal["read", "starred"],
) -> dict[str, Any]:
    """Finish a scope using message IDs, including when its flags change.

    Only adding read can skip already-read messages. Other operations must start
    at the oldest matching message, regardless of its read status.
    """
    anchor: int | Literal["first_unread", "oldest"] = (
        "first_unread" if op == "add" and flag == "read" else "oldest"
    )
    processed = updated = 0
    pages_completed = 0
    while True:
        try:
            result = await update_message_flags_for_narrow(
                narrow=narrow,
                op=op,
                flag=flag,
                anchor=anchor,
                include_anchor=isinstance(anchor, str),
                num_before=0,
                num_after=1000,
            )
        except Exception as exc:
            result = internal_error(exc)
        if result.get("status") != "success":
            return {
                **result,
                "status": "partial" if pages_completed else "error",
                "operation": f"{op}_{flag}",
                "processed_count": processed,
                "updated_count": updated,
                "pages_completed": pages_completed,
                "complete": False,
            }
        processed += result.get("processed_count", 0)
        updated += result.get("updated_count", 0)
        pages_completed += 1
        if result.get("found_newest") is True:
            return {
                **result,
                "processed_count": processed,
                "updated_count": updated,
                "pages_completed": pages_completed,
                "complete": True,
            }
        cursor = result.get("last_processed_id")
        if type(cursor) is not int or (isinstance(anchor, int) and cursor <= anchor):
            return {
                "status": "partial",
                "operation": f"{op}_{flag}",
                "error": error_object(
                    "Message flag pagination made no progress", "NO_PROGRESS"
                ),
                "processed_count": processed,
                "updated_count": updated,
                "pages_completed": pages_completed,
                "complete": False,
            }
        anchor = cursor


async def _flag_matching(
    op: Literal["add", "remove"],
    flag: Literal["read", "starred"],
    narrow: list[dict[str, Any]] | None,
    stream_id: int | str | None,
    topic_name: str | None,
    sender_email: str | None,
) -> dict[str, Any]:
    try:
        with bind_client(get_client()):
            built = narrow or _criteria_narrow(stream_id, topic_name, sender_email)
            if not built:
                return tool_error(
                    "Must provide narrow, stream_id, topic_name, or sender_email",
                    recovery_tool="mark_all_messages",
                    hint="To change every message, use mark_all_messages.",
                )
            return await _update_flag_pages(narrow=built, op=op, flag=flag)
    except Exception as e:
        return internal_error(e)


async def manage_message_flags(
    flag: Flag,
    action: Action,
    scope: Annotated[
        Literal["stream", "topic", "narrow"],
        Field(
            description="stream: one channel; topic: one channel topic; narrow: "
            "the narrow terms, or the stream_id/topic_name/sender_email filters."
        ),
    ] = "narrow",
    stream_id: Annotated[
        int | Name | None, Field(description="Channel ID or name.")
    ] = None,
    topic_name: Annotated[
        str | None, Field(max_length=60, description="Topic within stream_id.")
    ] = None,
    sender_email: Annotated[
        str | None,
        Field(max_length=254, description="Only messages from this sender."),
    ] = None,
    narrow: Annotated[
        list[dict[str, Any]] | None,
        Field(max_length=20, description="Zulip narrow terms (scope narrow)."),
    ] = None,
) -> dict[str, Any]:
    """Mark the entire matching scope read/unread or star/unstar.

    stream_id takes a channel ID or name. A partial result includes counts for
    completed pages when a later page fails.
    """
    if scope in ("stream", "topic") and not stream_id:
        return tool_error(f"stream_id required for scope='{scope}'")
    if scope == "topic" and not topic_name:
        return tool_error("topic_name required for scope='topic'")
    if scope == "stream":
        topic_name = sender_email = narrow = None
    elif scope == "topic":
        sender_email = narrow = None
    return await _flag_matching(
        action, flag, narrow, stream_id, topic_name, sender_email
    )


async def mark_all_messages(flag: Flag, action: Action) -> dict[str, Any]:
    """Set or clear a flag on every message the account can see."""
    try:
        with bind_client(get_client()):
            return await _update_flag_pages(narrow=[], op=action, flag=flag)
    except Exception as e:
        return internal_error(e)


async def get_read_receipts(message_id: MessageId) -> dict[str, Any]:
    """Users who have read a message, with names from the cached roster."""
    client = get_client()
    try:
        result = await asyncio.to_thread(
            client.client.call_endpoint,
            f"messages/{message_id}/read_receipts",
            method="GET",
            request={},
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to get read receipts")
        user_ids = result.get("user_ids", [])
        users = await asyncio.to_thread(client.get_users)
        names = {u.get("user_id"): u.get("full_name") for u in users.get("members", [])}
        return {
            "status": "success",
            "message_id": message_id,
            "readers": [{"user_id": uid, "name": names.get(uid)} for uid in user_ids],
            "count": len(user_ids),
        }
    except Exception as e:
        return internal_error(e)
