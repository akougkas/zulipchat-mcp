"""Messaging tools for ZulipChat MCP.

Optimized for latency with direct dict manipulation and minimal conversions.
"""

from datetime import datetime
from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.security import (
    sanitize_input,
    validate_emoji,
    validate_message_type,
    validate_stream_name,
    validate_topic,
)
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_message_sent, track_tool_call, track_tool_error

logger = get_logger(__name__)

# Maximum content size (50KB) - reasonable for most LLMs
MAX_CONTENT_SIZE = 50000

_client: ZulipClientWrapper | None = None


def _get_client(use_bot: bool = False) -> ZulipClientWrapper:
    """Get or create client instance."""
    global _client
    if _client is None:
        config = ConfigManager()
        _client = ZulipClientWrapper(config, use_bot_identity=use_bot)
    return _client


def _truncate_content(content: str) -> str:
    """Truncate content if it exceeds maximum size."""
    if len(content) > MAX_CONTENT_SIZE:
        return content[:MAX_CONTENT_SIZE] + "\n... [Content truncated]"
    return content


def send_message(
    message_type: str, to: str, content: str, topic: str | None = None
) -> dict[str, Any]:
    """Send a message to a Zulip stream or user with validation and metrics."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "send_message"}):
        with LogContext(logger, tool="send_message", message_type=message_type, to=to):
            track_tool_call("send_message")
            try:
                # Input validation (strict for agent inputs)
                if not validate_message_type(message_type):
                    return {
                        "status": "error",
                        "error": f"Invalid message_type: {message_type}",
                    }

                if message_type == "stream":
                    if not topic:
                        return {
                            "status": "error",
                            "error": "Topic required for stream messages",
                        }
                    if not validate_stream_name(to):
                        return {
                            "status": "error",
                            "error": f"Invalid stream name: {to}",
                        }
                    if not validate_topic(topic):
                        return {"status": "error", "error": f"Invalid topic: {topic}"}

                content = sanitize_input(content)

                client = _get_client()
                recipients = [to] if message_type == "private" else to
                result = client.send_message(message_type, recipients, content, topic)

                if result.get("result") == "success":
                    track_message_sent(message_type)
                    return {
                        "status": "success",
                        "message_id": result.get("id"),
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    return {
                        "status": "error",
                        "error": result.get("msg", "Unknown error"),
                    }

            except KeyError as e:
                track_tool_error("send_message", "KeyError")
                return {"status": "error", "error": f"Missing field: {e}"}
            except Exception as e:
                track_tool_error("send_message", type(e).__name__)
                return {"status": "error", "error": f"Failed to send: {str(e)}"}


def edit_message(
    message_id: int,
    content: str | None = None,
    topic: str | None = None,
    propagate_mode: str = "change_one",
    send_notification_to_old_thread: bool = False,
    send_notification_to_new_thread: bool = True,
    stream_id: int | None = None,
) -> dict[str, Any]:
    """Edit a message's content or topic."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "edit_message"}):
        with LogContext(logger, tool="edit_message", message_id=message_id):
            track_tool_call("edit_message")
            try:
                # Input validation
                if message_id <= 0:
                    return {"status": "error", "error": "Invalid message ID"}
                if not content and not topic and not stream_id:
                    return {
                        "status": "error",
                        "error": "Must provide content, topic, or stream_id to edit",
                    }
                if topic and not validate_topic(topic):
                    return {"status": "error", "error": "Invalid topic"}
                if content and stream_id:
                    return {
                        "status": "error",
                        "error": "Cannot update content and move stream simultaneously",
                    }
                if propagate_mode not in ["change_one", "change_later", "change_all"]:
                    return {"status": "error", "error": "Invalid propagate_mode"}

                safe_content = sanitize_input(content) if content else None
                client = _get_client()
                result = client.edit_message(
                    message_id,
                    safe_content,
                    topic,
                    propagate_mode=propagate_mode,
                    send_notification_to_old_thread=send_notification_to_old_thread,
                    send_notification_to_new_thread=send_notification_to_new_thread,
                    stream_id=stream_id,
                )

                if result.get("result") == "success":
                    return {"status": "success", "message": "Message edited"}
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to edit message"),
                }
            except KeyError as e:
                track_tool_error("edit_message", "KeyError")
                return {"status": "error", "error": f"Missing field: {e}"}
            except Exception as e:
                track_tool_error("edit_message", type(e).__name__)
                return {"status": "error", "error": f"Failed to edit: {str(e)}"}


def add_reaction(message_id: int, emoji_name: str) -> dict[str, Any]:
    """Add emoji reaction to a message."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "add_reaction"}):
        with LogContext(
            logger, tool="add_reaction", message_id=message_id, emoji=emoji_name
        ):
            track_tool_call("add_reaction")
            try:
                # Input validation
                if message_id <= 0:
                    return {"status": "error", "error": "Invalid message ID"}
                if not validate_emoji(emoji_name):
                    return {"status": "error", "error": "Invalid emoji name"}

                client = _get_client()
                result = client.add_reaction(message_id, emoji_name)

                if result.get("result") == "success":
                    return {"status": "success", "message": "Reaction added"}
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to add reaction"),
                }
            except KeyError as e:
                track_tool_error("add_reaction", "KeyError")
                return {"status": "error", "error": f"Missing field: {e}"}
            except Exception as e:
                track_tool_error("add_reaction", type(e).__name__)
                return {"status": "error", "error": f"Failed to add reaction: {str(e)}"}


def get_messages(
    anchor: str | int = "newest",
    num_before: int = 0,
    num_after: int = 100,
    narrow: list[dict[str, str]] | None = None,
    include_anchor: bool = True,
    client_gravatar: bool = True,
    apply_markdown: bool = True,
) -> dict[str, Any]:
    """Get messages from Zulip - optimized for latency."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_messages"}):
        with LogContext(logger, tool="get_messages", anchor=str(anchor)):
            track_tool_call("get_messages")
            try:
                # Input validation (strict for agent inputs)
                if isinstance(anchor, str) and anchor not in [
                    "newest",
                    "oldest",
                    "first_unread",
                ]:
                    return {"status": "error", "error": "Invalid anchor value"}
                if isinstance(anchor, int) and anchor <= 0:
                    return {"status": "error", "error": "Invalid message ID for anchor"}
                if num_before < 0 or num_after < 0:
                    return {
                        "status": "error",
                        "error": "num_before and num_after must be non-negative",
                    }
                if num_before + num_after > 5000:
                    return {
                        "status": "error",
                        "error": "Too many messages requested (max 5000)",
                    }

                client = _get_client()
                # Get raw response from Zulip
                response = client.get_messages_raw(
                    anchor=anchor,
                    num_before=num_before,
                    num_after=num_after,
                    narrow=narrow or [],
                    include_anchor=include_anchor,
                    client_gravatar=client_gravatar,
                    apply_markdown=apply_markdown,
                )

                # Quick validation
                if response.get("result") != "success":
                    return {
                        "status": "error",
                        "error": response.get("msg", "Failed to get messages"),
                    }

                # Extract only essential fields - no model creation
                messages = [
                    {
                        "id": msg["id"],
                        "sender": msg["sender_full_name"],
                        "email": msg["sender_email"],
                        "timestamp": msg["timestamp"],
                        "content": _truncate_content(msg["content"]),
                        "type": msg["type"],
                        "stream": msg.get("display_recipient"),
                        "topic": msg.get("subject"),
                        "reactions": msg.get("reactions", []),
                    }
                    for msg in response.get("messages", [])
                ]

                return {
                    "status": "success",
                    "messages": messages,
                    "count": len(messages),
                }

            except KeyError as e:
                track_tool_error("get_messages", "KeyError")
                logger.error(f"get_messages KeyError: {e}")
                return {"status": "error", "error": f"Missing expected field: {e}"}
            except Exception as e:
                track_tool_error("get_messages", type(e).__name__)
                logger.error(f"get_messages error: {type(e).__name__}: {str(e)}")
                return {"status": "error", "error": f"Failed to get messages: {str(e)}"}


def register_messaging_tools(mcp: Any) -> None:
    """Register messaging tools on the given MCP instance."""
    mcp.tool(description="Send a message to a Zulip stream or user")(send_message)
    mcp.tool(description="Edit an existing message")(edit_message)
    mcp.tool(description="Add emoji reaction to a message")(add_reaction)
    mcp.tool(description="Get messages from Zulip with filtering options")(get_messages)
