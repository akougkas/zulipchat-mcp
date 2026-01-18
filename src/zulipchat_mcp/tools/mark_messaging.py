"""Message marking tools for ZulipChat MCP v0.4.0.

Clean implementation of Zulip's message flag update API endpoints.
Uses modern "update personal message flags for narrow" instead of deprecated endpoints.
"""

from typing import Any, Literal

from fastmcp import FastMCP

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper


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
    config = ConfigManager()
    client = ZulipClientWrapper(config)

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

        result = client.client.call_endpoint(
            "messages/flags/narrow", method="POST", request=request_data
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
        # Use empty narrow to match all messages
        return await update_message_flags_for_narrow(
            narrow=[],
            op="add",
            flag="read",
            anchor="first_unread",
            num_before=0,
            num_after=1000,  # Large number to catch all unread
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mark_stream_as_read(stream_id: int) -> dict[str, Any]:
    """Mark all messages in a stream as read using modern narrow approach."""
    try:
        # Use stream narrow to match stream messages
        narrow = [{"operator": "stream", "operand": str(stream_id)}]

        return await update_message_flags_for_narrow(
            narrow=narrow,
            op="add",
            flag="read",
            anchor="first_unread",
            num_before=0,
            num_after=1000,
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mark_topic_as_read(stream_id: int, topic_name: str) -> dict[str, Any]:
    """Mark all messages in a topic as read using modern narrow approach."""
    try:
        # Use stream + topic narrow to match topic messages
        narrow = [
            {"operator": "stream", "operand": str(stream_id)},
            {"operator": "topic", "operand": topic_name},
        ]

        return await update_message_flags_for_narrow(
            narrow=narrow,
            op="add",
            flag="read",
            anchor="first_unread",
            num_before=0,
            num_after=1000,
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mark_messages_unread(
    narrow: list[dict[str, Any]] | None = None,
    stream_id: int | None = None,
    topic_name: str | None = None,
    sender_email: str | None = None,
) -> dict[str, Any]:
    """Mark messages as unread using flexible narrow construction."""
    try:
        # Build narrow from convenient parameters
        if not narrow:
            narrow = []
            if stream_id:
                narrow.append({"operator": "stream", "operand": str(stream_id)})
            if topic_name:
                narrow.append({"operator": "topic", "operand": topic_name})
            if sender_email:
                narrow.append({"operator": "sender", "operand": sender_email})

        if not narrow:
            return {
                "status": "error",
                "error": "Must provide narrow or stream_id/topic_name/sender_email",
            }

        return await update_message_flags_for_narrow(
            narrow=narrow,
            op="remove",
            flag="read",
            anchor="newest",
            num_before=100,
            num_after=0,
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
        # Build narrow from convenient parameters
        if not narrow:
            narrow = []
            if stream_id:
                narrow.append({"operator": "stream", "operand": str(stream_id)})
            if topic_name:
                narrow.append({"operator": "topic", "operand": topic_name})
            if sender_email:
                narrow.append({"operator": "sender", "operand": sender_email})

        if not narrow:
            return {
                "status": "error",
                "error": "Must provide narrow or stream_id/topic_name/sender_email",
            }

        return await update_message_flags_for_narrow(
            narrow=narrow,
            op="add",
            flag="starred",
            anchor="newest",
            num_before=100,
            num_after=0,
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
        # Build narrow from convenient parameters
        if not narrow:
            narrow = []
            if stream_id:
                narrow.append({"operator": "stream", "operand": str(stream_id)})
            if topic_name:
                narrow.append({"operator": "topic", "operand": topic_name})
            if sender_email:
                narrow.append({"operator": "sender", "operand": sender_email})

        if not narrow:
            return {
                "status": "error",
                "error": "Must provide narrow or stream_id/topic_name/sender_email",
            }

        return await update_message_flags_for_narrow(
            narrow=narrow,
            op="remove",
            flag="starred",
            anchor="newest",
            num_before=100,
            num_after=0,
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


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
