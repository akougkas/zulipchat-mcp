"""Core messaging tools for ZulipChat MCP v2.5.1.

Clean implementation focused ONLY on core send/edit operations.
Reactions moved to emoji_messaging.py, bulk ops moved to mark_messaging.py.
"""

from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


def sanitize_content(content: str, max_length: int = 50000) -> str:
    """Sanitize and truncate content."""
    if len(content) > max_length:
        return content[:max_length] + "\n... [Content truncated]"
    return content


async def send_message(
    type: Literal["stream", "private"],
    to: str | list[str],
    content: str,
    topic: str | None = None,
) -> dict[str, Any]:
    """Send a message to stream or user (immediate delivery only)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    # Validate stream messages have topic
    if type == "stream" and not topic:
        return {"status": "error", "error": "Topic required for stream messages"}

    # Content sanitization
    safe_content = sanitize_content(content)

    # Send immediate message
    result = client.send_message(type, to, safe_content, topic)

    if result.get("result") == "success":
        return {
            "status": "success",
            "message_id": result.get("id"),
            "timestamp": datetime.now().isoformat(),
        }
    else:
        return {"status": "error", "error": result.get("msg", "Failed to send message")}


async def edit_message(
    message_id: int,
    content: str | None = None,
    topic: str | None = None,
    stream_id: int | None = None,
    propagate_mode: Literal["change_one", "change_later", "change_all"] = "change_one",
    send_notification_to_old_thread: bool = False,
    send_notification_to_new_thread: bool = True,
) -> dict[str, Any]:
    """Edit message content, topic, or move between streams."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {
            "status": "error",
            "error": {
                "code": "INVALID_MESSAGE_ID",
                "message": f"Invalid message ID: {message_id}",
                "suggestions": ["Use search_messages to find valid message IDs"]
            }
        }

    if not content and not topic and not stream_id:
        return {"status": "error", "error": "Must provide content, topic, or stream_id to edit"}

    if propagate_mode not in ["change_one", "change_later", "change_all"]:
        return {
            "status": "error",
            "error": {
                "code": "INVALID_PROPAGATE_MODE",
                "message": f"Invalid propagate_mode: '{propagate_mode}'",
                "suggestions": [
                    "Use 'change_one' to edit only this message",
                    "Use 'change_later' to edit this and newer messages",
                    "Use 'change_all' to edit all messages in topic"
                ]
            }
        }

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    safe_content = sanitize_content(content) if content else None

    result = client.edit_message(
        message_id=message_id,
        content=safe_content,
        topic=topic,
        propagate_mode=propagate_mode,
        send_notification_to_old_thread=send_notification_to_old_thread,
        send_notification_to_new_thread=send_notification_to_new_thread,
        stream_id=stream_id,
    )

    if result.get("result") == "success":
        changes = []
        if content:
            changes.append("content")
        if topic:
            changes.append("topic")
        if stream_id:
            changes.append("stream")

        return {
            "status": "success",
            "message_id": message_id,
            "changes": changes,
            "propagate_mode": propagate_mode,
        }
    else:
        return {"status": "error", "error": result.get("msg", "Failed to edit message")}


async def get_message(message_id: int) -> dict[str, Any]:
    """Get a single message by ID."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {"status": "error", "error": "Invalid message ID"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_message(message_id)

        if result.get("result") == "success":
            return {
                "status": "success",
                "message": result.get("message", {}),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Message not found")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def cross_post_message(
    source_message_id: int,
    target_streams: list[str],
    target_topic: str | None = None,
    add_reference: bool = True,
    custom_prefix: str | None = None,
) -> dict[str, Any]:
    """Share/duplicate a message across multiple streams."""
    if not isinstance(source_message_id, int) or source_message_id <= 0:
        return {"status": "error", "error": "Invalid source message ID"}

    if not target_streams:
        return {"status": "error", "error": "Must specify target streams"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Get source message
        msg_result = await get_message(source_message_id)
        if msg_result.get("status") != "success":
            return {"status": "error", "error": "Source message not found"}

        source_msg = msg_result.get("message", {})
        source_content = source_msg.get("content", "")
        source_topic = source_msg.get("subject", "")
        source_stream = source_msg.get("display_recipient", "")

        # Prepare cross-post content
        if add_reference:
            prefix = custom_prefix or f"**Cross-posted from #{source_stream} > {source_topic}:**\n\n"
            cross_post_content = prefix + source_content
        else:
            cross_post_content = source_content

        safe_content = sanitize_content(cross_post_content)

        # Post to target streams
        results = []
        for stream in target_streams:
            post_topic = target_topic or source_topic

            send_result = await send_message("stream", stream, safe_content, post_topic)

            if send_result.get("status") == "success":
                results.append({
                    "stream": stream,
                    "topic": post_topic,
                    "message_id": send_result.get("message_id"),
                    "status": "success"
                })
            else:
                results.append({
                    "stream": stream,
                    "topic": post_topic,
                    "status": "error",
                    "error": send_result.get("error", "Failed to post")
                })

        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "error"]

        return {
            "status": "success" if not failed else "partial",
            "source_message_id": source_message_id,
            "target_streams": target_streams,
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_messaging_tools(mcp: FastMCP) -> None:
    """Register core messaging tools with the MCP server."""
    mcp.tool(name="send_message", description="Send message to stream or user (immediate delivery)")(send_message)
    mcp.tool(name="edit_message", description="Edit message content, topic, or move between streams with propagation control")(edit_message)
    mcp.tool(name="get_message", description="Get a single message by ID")(get_message)
    mcp.tool(name="cross_post_message", description="Share/duplicate message across multiple streams with attribution")(cross_post_message)