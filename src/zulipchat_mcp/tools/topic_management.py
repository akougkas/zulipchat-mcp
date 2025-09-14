"""Topic management tools for ZulipChat MCP v2.5.1.

Topic-specific operations: list, move, delete, mute, mark as read.
Clean API endpoint mapping without unnecessary complexity.
"""

from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


async def get_stream_topics(
    stream_id: int,
    max_results: int = 100,
) -> dict[str, Any]:
    """Get recent topics for a stream."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_stream_topics(stream_id)
        if result.get("result") == "success":
            topics = result.get("topics", [])

            return {
                "status": "success",
                "stream_id": stream_id,
                "topics": topics[:max_results],
                "count": len(topics),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to list topics")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def move_topic(
    stream_id: int,
    source_topic: str,
    target_topic: str,
    target_stream_id: int | None = None,
    propagate_mode: str = "change_all",
    send_notification_to_new_thread: bool = True,
    send_notification_to_old_thread: bool = True,
) -> dict[str, Any]:
    """Move topic within stream or to different stream."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Find a message in the source topic to trigger the move
        from .search import search_messages

        # Build narrow to find messages in source topic
        narrow = [
            {"operator": "stream", "operand": str(stream_id)},
            {"operator": "topic", "operand": source_topic}
        ]

        search_result = client.get_messages_raw(narrow=narrow, num_before=1, num_after=0)

        if search_result.get("result") != "success" or not search_result.get("messages"):
            return {"status": "error", "error": "No messages found in source topic to move"}

        # Get the first message to trigger the move
        first_message = search_result["messages"][0]
        message_id = first_message["id"]

        # Use edit_message to move the topic
        from .messaging import edit_message
        edit_result = await edit_message(
            message_id=message_id,
            topic=target_topic,
            stream_id=target_stream_id,
            propagate_mode=propagate_mode,
            send_notification_to_old_thread=send_notification_to_old_thread,
            send_notification_to_new_thread=send_notification_to_new_thread,
        )

        if edit_result.get("status") == "success":
            return {
                "status": "success",
                "source_stream_id": stream_id,
                "target_stream_id": target_stream_id or stream_id,
                "source_topic": source_topic,
                "target_topic": target_topic,
                "propagate_mode": propagate_mode,
                "messages_moved": "all" if propagate_mode == "change_all" else "partial",
            }
        else:
            return {"status": "error", "error": edit_result.get("error", "Failed to move topic")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def delete_topic(stream_id: int, topic_name: str) -> dict[str, Any]:
    """Delete a topic from a stream."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.delete_topic(stream_id, topic_name)
        if result.get("result") == "success":
            return {
                "status": "success",
                "stream_id": stream_id,
                "topic_name": topic_name,
                "action": "deleted",
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to delete topic")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mute_topic(stream_id: int, topic_name: str) -> dict[str, Any]:
    """Mute a topic for your own notifications."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.mute_topic(stream_id, topic_name)
        if result.get("result") == "success":
            return {
                "status": "success",
                "stream_id": stream_id,
                "topic_name": topic_name,
                "action": "muted",
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to mute topic")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def unmute_topic(stream_id: int, topic_name: str) -> dict[str, Any]:
    """Unmute a topic for your own notifications."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.unmute_topic(stream_id, topic_name)
        if result.get("result") == "success":
            return {
                "status": "success",
                "stream_id": stream_id,
                "topic_name": topic_name,
                "action": "unmuted",
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to unmute topic")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_topic_management_tools(mcp: FastMCP) -> None:
    """Register topic management tools with the MCP server."""
    mcp.tool(name="get_stream_topics", description="Get recent topics for a stream")(get_stream_topics)
    mcp.tool(name="move_topic", description="Move topic within stream or to different stream")(move_topic)
    mcp.tool(name="delete_topic", description="Delete a topic from a stream")(delete_topic)
    mcp.tool(name="mute_topic", description="Mute a topic for your own notifications")(mute_topic)
    mcp.tool(name="unmute_topic", description="Unmute a topic for your own notifications")(unmute_topic)