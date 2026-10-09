"""Message marking tools for ZulipChat MCP v0.4.0.

Clean implementation of Zulip's message flag update API endpoints.
Uses modern "update personal message flags for narrow" instead of deprecated endpoints.
"""

import asyncio
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import bind_client, get_client


def _resolve_stream_name(stream_id: int) -> str:
    """Resolve stream ID to name using Zulip API."""
    client = get_client()
    # Fetch all streams and find the one with matching ID
    # This is more reliable than the streams/{id} endpoint
    result = client.get_streams(include_public=True, include_subscribed=True)
    if result.get("result") == "success":
        for stream in result.get("streams", []):
            if stream.get("stream_id") == stream_id:
                return stream["name"]
    raise ValueError(f"Unknown stream ID: {stream_id}")


async def update_message_flags_for_narrow(
    narrow: list[dict[str, Any]],
    op: Literal["add", "remove"],
    flag: str,
    anchor: int | Literal["first_unread", "oldest", "newest"] = "newest",
    include_anchor: bool = True,
    num_before: int = 50,
    num_after: int = 50,
) -> dict[str, Any]:
    """Update personal message flags for messages matching a narrow (modern approach)."""
    client = get_client()

    try:
        request_data = {
            "narrow": narrow,
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
            return {
                "status": "error",
                "error": result.get("msg", "Failed to update message flags"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mark_all_as_read() -> dict[str, Any]:
    """Mark all messages as read using modern narrow approach."""
    try:
        with bind_client(get_client()):
            # Use empty narrow to match all messages
            return await _mark_read_pages([])
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mark_stream_as_read(stream_id: int) -> dict[str, Any]:
    """Mark all messages in a stream as read using modern narrow approach."""
    try:
        with bind_client(get_client()):
            stream_name = await asyncio.to_thread(_resolve_stream_name, stream_id)
            # Use stream narrow to match stream messages
            narrow = [{"operator": "stream", "operand": stream_name}]

            return await _mark_read_pages(narrow)
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mark_topic_as_read(stream_id: int, topic_name: str) -> dict[str, Any]:
    """Mark all messages in a topic as read using modern narrow approach."""
    try:
        with bind_client(get_client()):
            stream_name = await asyncio.to_thread(_resolve_stream_name, stream_id)
            # Use stream + topic narrow to match topic messages
            narrow = [
                {"operator": "stream", "operand": stream_name},
                {"operator": "topic", "operand": topic_name},
            ]

            return await _mark_read_pages(narrow)
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _mark_read_pages(narrow: list[dict[str, Any]]) -> dict[str, Any]:
    """Compatibility wrapper for the shared bulk flag operation."""
    return await _update_flag_pages(narrow, "add", "read")


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
            result = {"status": "error", "error": str(exc)}
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
                "error": "Message flag pagination made no progress",
                "processed_count": processed,
                "updated_count": updated,
                "pages_completed": pages_completed,
                "complete": False,
            }
        anchor = cursor


async def mark_messages_unread(
    narrow: list[dict[str, Any]] | None = None,
    stream_id: int | None = None,
    topic_name: str | None = None,
    sender_email: str | None = None,
) -> dict[str, Any]:
    """Mark messages as unread using flexible narrow construction."""
    try:
        with bind_client(get_client()):
            # Build narrow from convenient parameters
            if not narrow:
                narrow = []
                if stream_id:
                    try:
                        stream_name = await asyncio.to_thread(
                            _resolve_stream_name, stream_id
                        )
                        narrow.append({"operator": "stream", "operand": stream_name})
                    except ValueError as e:
                        return {"status": "error", "error": str(e)}
                if topic_name:
                    narrow.append({"operator": "topic", "operand": topic_name})
                if sender_email:
                    narrow.append({"operator": "sender", "operand": sender_email})

            if not narrow:
                return {
                    "status": "error",
                    "error": "Must provide narrow or stream_id/topic_name/sender_email",
                }

            return await _update_flag_pages(
                narrow=narrow,
                op="remove",
                flag="read",
            )
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def star_messages(
    narrow: list[dict[str, Any]] | None = None,
    stream_id: int | None = None,
    topic_name: str | None = None,
    sender_email: str | None = None,
) -> dict[str, Any]:
    """Star messages matching criteria."""
    try:
        with bind_client(get_client()):
            # Build narrow from convenient parameters
            if not narrow:
                narrow = []
                if stream_id:
                    try:
                        stream_name = await asyncio.to_thread(
                            _resolve_stream_name, stream_id
                        )
                        narrow.append({"operator": "stream", "operand": stream_name})
                    except ValueError as e:
                        return {"status": "error", "error": str(e)}
                if topic_name:
                    narrow.append({"operator": "topic", "operand": topic_name})
                if sender_email:
                    narrow.append({"operator": "sender", "operand": sender_email})

            if not narrow:
                return {
                    "status": "error",
                    "error": "Must provide narrow or stream_id/topic_name/sender_email",
                }

            return await _update_flag_pages(
                narrow=narrow,
                op="add",
                flag="starred",
            )
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def unstar_messages(
    narrow: list[dict[str, Any]] | None = None,
    stream_id: int | None = None,
    topic_name: str | None = None,
    sender_email: str | None = None,
) -> dict[str, Any]:
    """Unstar messages matching criteria."""
    try:
        with bind_client(get_client()):
            # Build narrow from convenient parameters
            if not narrow:
                narrow = []
                if stream_id:
                    try:
                        stream_name = await asyncio.to_thread(
                            _resolve_stream_name, stream_id
                        )
                        narrow.append({"operator": "stream", "operand": stream_name})
                    except ValueError as e:
                        return {"status": "error", "error": str(e)}
                if topic_name:
                    narrow.append({"operator": "topic", "operand": topic_name})
                if sender_email:
                    narrow.append({"operator": "sender", "operand": sender_email})

            if not narrow:
                return {
                    "status": "error",
                    "error": "Must provide narrow or stream_id/topic_name/sender_email",
                }

            return await _update_flag_pages(
                narrow=narrow,
                op="remove",
                flag="starred",
            )
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def manage_message_flags(
    flag: Literal["read", "starred"],
    action: Literal["add", "remove"],
    scope: Literal["all", "stream", "topic", "narrow"] = "narrow",
    stream_id: int | None = None,
    topic_name: str | None = None,
    sender_email: str | None = None,
    narrow: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mark the entire matching scope read/unread or star/unstar.

    A partial result includes counts for completed pages when a later page fails.
    """
    with bind_client(get_client()):
        if scope == "all":
            return await _update_flag_pages(
                narrow=[],
                op=action,
                flag=flag,
            )
        elif scope == "stream":
            if not stream_id:
                return {
                    "status": "error",
                    "error": "stream_id required for scope='stream'",
                }
            try:
                stream_name = await asyncio.to_thread(_resolve_stream_name, stream_id)
            except ValueError as e:
                return {"status": "error", "error": str(e)}
            return await _update_flag_pages(
                narrow=[{"operator": "stream", "operand": stream_name}],
                op=action,
                flag=flag,
            )
        elif scope == "topic":
            if not stream_id:
                return {
                    "status": "error",
                    "error": "stream_id required for scope='topic'",
                }
            if not topic_name:
                return {
                    "status": "error",
                    "error": "topic_name required for scope='topic'",
                }
            try:
                stream_name = await asyncio.to_thread(_resolve_stream_name, stream_id)
            except ValueError as e:
                return {"status": "error", "error": str(e)}
            return await _update_flag_pages(
                narrow=[
                    {"operator": "stream", "operand": stream_name},
                    {"operator": "topic", "operand": topic_name},
                ],
                op=action,
                flag=flag,
            )
        else:  # scope == "narrow"
            built_narrow: list[dict[str, Any]] = narrow or []
            if not built_narrow:
                if stream_id:
                    try:
                        stream_name = await asyncio.to_thread(
                            _resolve_stream_name, stream_id
                        )
                        built_narrow.append(
                            {"operator": "stream", "operand": stream_name}
                        )
                    except ValueError as e:
                        return {"status": "error", "error": str(e)}
                if topic_name:
                    built_narrow.append({"operator": "topic", "operand": topic_name})
                if sender_email:
                    built_narrow.append({"operator": "sender", "operand": sender_email})
            if not built_narrow:
                return {
                    "status": "error",
                    "error": "Must provide narrow, stream_id, topic_name, or sender_email",
                }
            return await _update_flag_pages(
                narrow=built_narrow,
                op=action,
                flag=flag,
            )


def register_mark_messaging_tools(mcp: FastMCP) -> None:
    """Register message marking tools with the MCP server."""
    mcp.tool(
        name="update_message_flags_for_narrow",
        description="Update personal message flags for messages matching a narrow (modern approach)",
    )(update_message_flags_for_narrow)
    mcp.tool(
        name="mark_all_as_read",
        description="Mark all messages as read using modern narrow approach",
    )(mark_all_as_read)
    mcp.tool(
        name="mark_stream_as_read", description="Mark all messages in a stream as read"
    )(mark_stream_as_read)
    mcp.tool(
        name="mark_topic_as_read", description="Mark all messages in a topic as read"
    )(mark_topic_as_read)
    mcp.tool(
        name="mark_messages_unread",
        description="Mark messages as unread using flexible narrow construction",
    )(mark_messages_unread)
    mcp.tool(name="star_messages", description="Star messages matching criteria")(
        star_messages
    )
    mcp.tool(name="unstar_messages", description="Unstar messages matching criteria")(
        unstar_messages
    )
