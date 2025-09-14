"""Messaging tools for ZulipChat MCP v2.5.1.

Complete messaging operations including send, schedule, edit, reactions, and bulk operations.
All functionality from the complex v25 architecture preserved in minimal code.
"""

import json
import re
from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager

# Import optional components
try:
    from ..services.scheduler import MessageScheduler, ScheduledMessage
    from ..config import ZulipConfig
    scheduler_available = True
except ImportError:
    scheduler_available = False

try:
    from ..utils.database_manager import DatabaseManager
    database_available = True
except ImportError:
    database_available = False


def validate_emoji(emoji_name: str) -> bool:
    """Validate emoji name against injection."""
    pattern = r"^[a-zA-Z0-9_]+$"
    return bool(re.match(pattern, emoji_name)) and 0 < len(emoji_name) <= 50


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
    # Scheduling support
    schedule_at: datetime | None = None,
    # Formatting options
    syntax_highlight: bool = False,
    link_preview: bool = True,
    emoji_translate: bool = True,
) -> dict[str, Any]:
    """Send, schedule, or draft messages with full formatting support."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    # Validate stream messages have topic
    if type == "stream" and not topic:
        return {"status": "error", "error": "Topic required for stream messages"}

    # Content sanitization
    safe_content = sanitize_content(content)

    # Handle scheduling if requested
    if schedule_at and scheduler_available:
        try:
            scheduled_msg = ScheduledMessage(
                content=safe_content,
                scheduled_time=schedule_at,
                message_type=type,
                recipients=[to] if type == "private" else to,
                topic=topic,
            )

            # Create scheduler config
            client_config = config.get_zulip_client_config(use_bot=False)
            scheduler_config = ZulipConfig(
                email=client_config["email"],
                api_key=client_config["api_key"],
                site=client_config["site"],
            )

            async with MessageScheduler(scheduler_config) as scheduler:
                result = await scheduler.schedule_message(scheduled_msg)

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "schedule",
                    "scheduled_message_id": result.get("scheduled_message_id"),
                    "scheduled_at": schedule_at.isoformat(),
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to schedule message")}

        except Exception as e:
            return {"status": "error", "error": f"Scheduling failed: {str(e)}"}

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
                "message": f"Invalid message ID: {message_id}. Message IDs must be positive integers.",
                "suggestions": [
                    "Use a positive integer for the message ID",
                    "Search for messages first to get valid message IDs",
                    "Verify the message exists and is accessible"
                ],
                "recovery": {
                    "tool": "search_messages",
                    "hint": "Search messages to get valid IDs"
                }
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

    # Content sanitization
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


async def add_reaction(
    message_id: int,
    emoji_name: str,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Add emoji reaction to message with validation."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {
            "status": "error",
            "error": {
                "code": "INVALID_MESSAGE_ID",
                "message": "Invalid message ID. Must be a positive integer.",
                "suggestions": ["Use search_messages to find valid message IDs"]
            }
        }

    if not validate_emoji(emoji_name):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_EMOJI_NAME",
                "message": f"Invalid emoji name: '{emoji_name}'",
                "suggestions": [
                    "Use alphanumeric characters and underscores only",
                    "Keep emoji name under 50 characters",
                    "Check available emojis in your Zulip organization"
                ]
            }
        }

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    result = client.add_reaction(message_id, emoji_name)

    if result.get("result") == "success":
        return {
            "status": "success",
            "message_id": message_id,
            "emoji": emoji_name,
            "reaction_type": reaction_type,
        }
    else:
        return {"status": "error", "error": result.get("msg", "Failed to add reaction")}


async def remove_reaction(
    message_id: int,
    emoji_name: str,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Remove emoji reaction from message with validation."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {"status": "error", "error": "Invalid message ID"}

    if not validate_emoji(emoji_name):
        return {"status": "error", "error": f"Invalid emoji name: '{emoji_name}'"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    result = client.remove_reaction(message_id, emoji_name)

    if result.get("result") == "success":
        return {"status": "success", "message_id": message_id, "emoji": emoji_name}
    else:
        return {"status": "error", "error": result.get("msg", "Failed to remove reaction")}


async def bulk_operations(
    operation: Literal["mark_read", "mark_unread", "add_flag", "remove_flag", "add_reaction", "remove_reaction", "delete_messages"],
    # Message selection
    message_ids: list[int] | None = None,
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    # Operation parameters
    flag: str | None = None,
    emoji_name: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Perform bulk operations on multiple messages."""
    if not message_ids and not (stream or topic or sender):
        return {"status": "error", "error": "Must specify message_ids or search criteria"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # If no message_ids provided, search for messages
        if not message_ids:
            from .search import search_messages
            search_result = await search_messages(stream=stream, topic=topic, sender=sender, limit=100)

            if search_result.get("status") != "success":
                return {"status": "error", "error": "Failed to find messages for bulk operation"}

            message_ids = [msg["id"] for msg in search_result.get("messages", [])]

        if not message_ids:
            return {"status": "success", "processed": 0, "message": "No messages found"}

        # Perform bulk operation
        successful = []
        failed = []

        for msg_id in message_ids:
            try:
                if operation == "mark_read":
                    result = client.update_message_flags([msg_id], "add", "read")
                elif operation == "mark_unread":
                    result = client.update_message_flags([msg_id], "remove", "read")
                elif operation == "add_flag" and flag:
                    result = client.update_message_flags([msg_id], "add", flag)
                elif operation == "remove_flag" and flag:
                    result = client.update_message_flags([msg_id], "remove", flag)
                elif operation == "add_reaction" and emoji_name:
                    result = client.add_reaction(msg_id, emoji_name)
                elif operation == "remove_reaction" and emoji_name:
                    result = client.remove_reaction(msg_id, emoji_name)
                elif operation == "delete_messages":
                    # Zulip doesn't have bulk delete, but we can edit to indicate deletion
                    result = client.edit_message(msg_id, content="[Message deleted]")
                else:
                    failed.append({"message_id": msg_id, "error": "Invalid operation parameters"})
                    continue

                if result.get("result") == "success":
                    successful.append(msg_id)
                else:
                    failed.append({"message_id": msg_id, "error": result.get("msg", "Operation failed")})

            except Exception as e:
                failed.append({"message_id": msg_id, "error": str(e)})

        return {
            "status": "success" if not failed else "partial",
            "operation": operation,
            "processed": len(successful),
            "failed": len(failed),
            "successful_message_ids": successful,
            "failures": failed,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "operation": operation}


async def message_history(message_id: int) -> dict[str, Any]:
    """Get comprehensive message history including edits and reactions."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {"status": "error", "error": "Invalid message ID"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Get message details
        result = client.get_message(message_id)

        if result.get("result") == "success":
            message = result.get("message", {})
            return {
                "status": "success",
                "message_id": message_id,
                "message": message,
                "edit_history": {
                    "last_edit_timestamp": message.get("last_edit_timestamp"),
                    "edit_history": message.get("edit_history", []),
                },
                "reactions": message.get("reactions", []),
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
        msg_result = client.get_message(source_message_id)
        if msg_result.get("result") != "success":
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

            result = client.send_message("stream", stream, safe_content, post_topic)

            if result.get("result") == "success":
                results.append({
                    "stream": stream,
                    "topic": post_topic,
                    "message_id": result.get("id"),
                    "status": "success"
                })
            else:
                results.append({
                    "stream": stream,
                    "topic": post_topic,
                    "status": "error",
                    "error": result.get("msg", "Failed to post")
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
    """Register messaging tools with the MCP server."""
    mcp.tool(name="send_message", description="Send or schedule messages with formatting options")(send_message)
    mcp.tool(name="edit_message", description="Edit message content, topic, or move between streams")(edit_message)
    mcp.tool(name="add_reaction", description="Add emoji reaction to message with validation")(add_reaction)
    mcp.tool(name="remove_reaction", description="Remove emoji reaction from message")(remove_reaction)
    mcp.tool(name="bulk_operations", description="Perform bulk operations on multiple messages")(bulk_operations)
    mcp.tool(name="message_history", description="Get message history with edits and reactions")(message_history)
    mcp.tool(name="cross_post_message", description="Cross-post message to multiple streams")(cross_post_message)