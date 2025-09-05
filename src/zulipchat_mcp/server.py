"""Enhanced MCP server for Zulip integration with security and error handling."""

import logging
import os
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ConfigManager
from .exceptions import ConnectionError, create_error_response

# Import structured logging
from .logging_config import LogContext, get_logger, setup_structured_logging

# Import notifications
from .notifications import NotificationPriority, smart_notify

# Import scheduler
from .scheduler import MessageScheduler, ScheduledMessage

# Import assistant tools to register them with FastMCP

# Set up structured logging
setup_structured_logging()
logger = get_logger(__name__)

# Initialize FastMCP server
mcp = FastMCP("ZulipChat MCP")

# Global client instance
zulip_client = None
config_manager = None


# Import security functions
# Import health monitoring
# Import metrics collection
from .metrics import Timer, track_message_sent, track_tool_call, track_tool_error
from .security import (
    sanitize_input,
    validate_message_type,
    validate_stream_name,
    validate_topic,
)


def get_client() -> Any:
    """Get or create Zulip client instance with user credentials."""
    global zulip_client, config_manager
    if zulip_client is None:
        from .client import ZulipClientWrapper
        from .config import ConfigManager

        config_manager = ConfigManager()
        zulip_client = ZulipClientWrapper(config_manager, use_bot_identity=False)
    return zulip_client


def get_bot_client() -> Any:
    """Get or create Zulip client instance with bot credentials."""
    global config_manager
    from .client import ZulipClientWrapper
    from .config import ConfigManager

    if config_manager is None:
        config_manager = ConfigManager()
    # Create bot client - will use bot credentials if available
    return ZulipClientWrapper(config_manager, use_bot_identity=True)


@mcp.tool()
def send_message(
    message_type: str, to: str, content: str, topic: str | None = None
) -> dict[str, Any]:
    """Send a message to a Zulip stream or user with enhanced security.

    Args:
        message_type: Type of message ("stream" or "private")
        to: Stream name or user email/username
        content: Message content
        topic: Topic name (required for stream messages)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "send_message"}):
        with LogContext(logger, tool="send_message", message_type=message_type, to=to):
            track_tool_call("send_message")
            try:
                # Validate inputs
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

                # Sanitize content
                content = sanitize_input(content)

                # Get client and send message
                client = get_client()
                recipients = [to] if message_type == "private" else to
                result = client.send_message(message_type, recipients, content, topic)

                # Track successful message send
                if result.get("result") == "success":
                    track_message_sent(message_type)

                # Add metadata to response
                if result.get("result") == "success":
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

            except ValueError as e:
                track_tool_error("send_message", "ValueError")
                return create_error_response(e, "send_message", {"to": to})
            except Exception as e:
                track_tool_error("send_message", "Exception")
                return create_error_response(e, "send_message")


# Scheduler endpoints
@mcp.tool()
async def schedule_message(
    content: str,
    scheduled_time: str,
    message_type: str,
    to: str,
    topic: str | None = None,
) -> dict[str, Any]:
    """Schedule a message to be sent at a future time.

    Args:
        content: Message content
        scheduled_time: ISO format datetime string (e.g., '2024-01-01T12:00:00')
        message_type: 'stream' or 'private'
        to: Stream name or user email
        topic: Topic name (required for stream messages)

    Returns:
        Scheduling result with scheduled message ID
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "schedule_message"}):
        with LogContext(
            logger, tool="schedule_message", message_type=message_type, to=to
        ):
            track_tool_call("schedule_message")
            try:
                # Parse scheduled time
                try:
                    scheduled_dt = datetime.fromisoformat(
                        scheduled_time.replace("Z", "+00:00")
                    )
                except ValueError as e:
                    return {"status": "error", "error": f"Invalid datetime format: {e}"}

                # Validate inputs
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

                # Sanitize content
                content = sanitize_input(content)

                # Create scheduled message
                message = ScheduledMessage(
                    content=content,
                    scheduled_time=scheduled_dt,
                    message_type=message_type,
                    recipients=to,
                    topic=topic,
                    scheduled_id=None,  # Will be set by API
                )

                # Get config and schedule
                global config_manager
                if config_manager is None:
                    config_manager = ConfigManager()
                config = config_manager.config
                async with MessageScheduler(config) as scheduler:
                    result = await scheduler.schedule_message(message)

                if result.get("result") == "success":
                    return {
                        "status": "success",
                        "scheduled_id": result.get("scheduled_message_id"),
                        "scheduled_time": scheduled_time,
                    }
                else:
                    return {
                        "status": "error",
                        "error": result.get("msg", "Unknown error"),
                    }

            except ValueError as e:
                track_tool_error("schedule_message", "ValueError")
                return create_error_response(
                    e, "schedule_message", {"scheduled_time": scheduled_time}
                )
            except Exception as e:
                track_tool_error("schedule_message", "Exception")
                return create_error_response(e, "schedule_message")


@mcp.tool()
async def cancel_scheduled(scheduled_id: int) -> dict[str, Any]:
    """Cancel a scheduled message.

    Args:
        scheduled_id: ID of the scheduled message to cancel

    Returns:
        Cancellation result
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "cancel_scheduled"}):
        with LogContext(logger, tool="cancel_scheduled", scheduled_id=scheduled_id):
            track_tool_call("cancel_scheduled")
            try:
                config = get_client().config_manager.config
                async with MessageScheduler(config) as scheduler:
                    result = await scheduler.cancel_scheduled(scheduled_id)

                if result.get("result") == "success":
                    return {
                        "status": "success",
                        "message": "Scheduled message cancelled",
                    }
                else:
                    return {
                        "status": "error",
                        "error": result.get("msg", "Unknown error"),
                    }

            except Exception as e:
                track_tool_error("cancel_scheduled", "Exception")
                return create_error_response(
                    e, "cancel_scheduled", {"scheduled_id": scheduled_id}
                )


@mcp.tool()
async def list_scheduled() -> list[dict[str, Any]]:
    """List all scheduled messages.

    Returns:
        List of scheduled messages with their details
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "list_scheduled"}):
        with LogContext(logger, tool="list_scheduled"):
            track_tool_call("list_scheduled")
            try:
                config = get_client().config_manager.config
                async with MessageScheduler(config) as scheduler:
                    messages = await scheduler.list_scheduled()

                return [
                    {
                        "id": msg["scheduled_message_id"],
                        "content": (
                            msg["content"][:100] + "..."
                            if len(msg["content"]) > 100
                            else msg["content"]
                        ),
                        "scheduled_time": datetime.fromtimestamp(
                            msg["scheduled_delivery_timestamp"]
                        ).isoformat(),
                        "type": msg["type"],
                        "to": msg["to"],
                        "topic": msg.get("topic"),
                    }
                    for msg in messages
                ]

            except Exception as e:
                track_tool_error("list_scheduled", "Exception")
                logger.error(f"Error in list_scheduled: {e}")
                return [{"error": f"Failed to retrieve scheduled messages: {str(e)}"}]


# Notifications endpoint
@mcp.tool()
async def send_notification(
    recipients: str, content: str, priority: str = "medium"
) -> dict[str, Any]:
    """Send smart notification with priority-based routing.

    Args:
        recipients: Comma-separated list of recipient emails
        content: Notification content
        priority: Priority level (low, medium, high, urgent)

    Returns:
        Notification result with delivery status
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "send_notification"}):
        with LogContext(
            logger, tool="send_notification", recipients=recipients, priority=priority
        ):
            track_tool_call("send_notification")
            try:
                # Parse recipients
                recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]

                if not recipient_list:
                    return {"status": "error", "error": "No valid recipients provided"}

                # Validate priority
                try:
                    notification_priority = NotificationPriority(priority.lower())
                except ValueError:
                    return {"status": "error", "error": f"Invalid priority: {priority}"}

                # Sanitize content
                content = sanitize_input(content)

                # Get config and send notification
                global config_manager
                if config_manager is None:
                    config_manager = ConfigManager()
                config = config_manager.config

                result = await smart_notify(
                    config, recipient_list, content, notification_priority
                )

                return {
                    "status": "success",
                    "priority": priority,
                    "recipients": recipient_list,
                    "result": result,
                }

            except Exception as e:
                track_tool_error("send_notification", "Exception")
                return create_error_response(e, "send_notification")


@mcp.tool()
def get_messages(
    stream_name: str | None = None,
    topic: str | None = None,
    hours_back: int = 24,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get messages from Zulip streams.

    Args:
        stream_name: Name of the stream (None for all streams)
        topic: Filter by topic (optional)
        hours_back: How many hours back to fetch (default: 24)
        limit: Maximum messages to return (default: 100)
    """
    # Validate inputs before any operations
    if stream_name and not validate_stream_name(stream_name):
        return [{"error": f"Invalid stream name: {stream_name}"}]
    if topic and not validate_topic(topic):
        return [{"error": f"Invalid topic: {topic}"}]
    if hours_back < 1 or hours_back > 168:  # Max 1 week
        return [{"error": "hours_back must be between 1 and 168"}]
    if limit < 1 or limit > 100:
        return [{"error": "limit must be between 1 and 100"}]

    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_messages"}):
        with LogContext(logger, tool="get_messages", stream=stream_name):
            track_tool_call("get_messages")
            try:

                # Get messages
                client = get_client()

                # If no stream_name and no topic, use generic get_messages
                if stream_name is None and topic is None:
                    # Call the base get_messages method
                    if hasattr(client, "get_messages"):
                        messages = client.get_messages(num_before=limit)
                    else:
                        messages = client.get_messages_from_stream(
                            stream_name, topic, hours_back, limit
                        )
                else:
                    messages = client.get_messages_from_stream(
                        stream_name, topic, hours_back, limit
                    )

                # Handle both ZulipMessage objects and dicts
                if messages and hasattr(messages[0], "id"):
                    # Convert ZulipMessage objects to dicts
                    return [
                        {
                            "id": msg.id if hasattr(msg, "id") else msg.get("id"),
                            "content": (
                                msg.content
                                if hasattr(msg, "content")
                                else msg.get("content")
                            ),
                            "sender": (
                                msg.sender_full_name
                                if hasattr(msg, "sender_full_name")
                                else msg.get("sender")
                            ),
                            "email": (
                                msg.sender_email
                                if hasattr(msg, "sender_email")
                                else msg.get("email")
                            ),
                            "timestamp": (
                                msg.timestamp
                                if hasattr(msg, "timestamp")
                                else msg.get("timestamp")
                            ),
                            "stream": (
                                msg.stream_name
                                if hasattr(msg, "stream_name")
                                else msg.get("stream")
                            ),
                            "topic": (
                                msg.subject
                                if hasattr(msg, "subject")
                                else msg.get("topic")
                            ),
                            "type": (
                                msg.type if hasattr(msg, "type") else msg.get("type")
                            ),
                        }
                        for msg in messages
                    ]
                return messages

            except ConnectionError as e:
                track_tool_error("get_messages", "ConnectionError")
                logger.error(f"Connection error in get_messages: {e}")
                return [{"error": f"Failed to retrieve messages: {str(e)}"}]
            except Exception as e:
                track_tool_error("get_messages", "Exception")
                logger.error(f"Error in get_messages: {e}")
                return [{"error": str(e)}]


@mcp.tool()
def search_messages(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Search messages across all accessible streams.

    Args:
        query: Search query string
        limit: Maximum results to return (default: 50)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "search_messages"}):
        with LogContext(logger, tool="search_messages", query=query[:50]):
            track_tool_call("search_messages")
            try:
                # Validate inputs
                if not query or not query.strip():
                    return [{"error": "Query cannot be empty"}]
                if limit < 1 or limit > 100:
                    return [{"error": "limit must be between 1 and 100"}]

                # Sanitize query
                query = sanitize_input(query)

                # Search messages
                client = get_client()
                results = client.search_messages(query, num_results=limit)

                # Handle both ZulipMessage objects and dicts
                if results and hasattr(results[0], "id"):
                    # Convert ZulipMessage objects to dicts
                    return [
                        {
                            "id": msg.id if hasattr(msg, "id") else msg.get("id"),
                            "content": (
                                msg.content
                                if hasattr(msg, "content")
                                else msg.get("content")
                            ),
                            "sender": (
                                msg.sender_full_name
                                if hasattr(msg, "sender_full_name")
                                else msg.get("sender")
                            ),
                            "email": (
                                msg.sender_email
                                if hasattr(msg, "sender_email")
                                else msg.get("email")
                            ),
                            "timestamp": (
                                msg.timestamp
                                if hasattr(msg, "timestamp")
                                else msg.get("timestamp")
                            ),
                            "stream": (
                                msg.stream_name
                                if hasattr(msg, "stream_name")
                                else msg.get("stream")
                            ),
                            "topic": (
                                msg.subject
                                if hasattr(msg, "subject")
                                else msg.get("topic")
                            ),
                            "type": (
                                msg.type if hasattr(msg, "type") else msg.get("type")
                            ),
                        }
                        for msg in results
                    ]
                return results

            except Exception as e:
                track_tool_error("search_messages", "Exception")
                logger.error(f"Error in search_messages: {e}")
                return [{"error": str(e)}]


@mcp.tool()
def get_streams() -> list[dict[str, Any]]:
    """Get list of all accessible Zulip streams."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_streams"}):
        with LogContext(logger, tool="get_streams"):
            track_tool_call("get_streams")
            try:
                # Get stream list
                client = get_client()
                streams = client.get_streams()

                # Handle both ZulipStream objects and dicts
                if streams and hasattr(streams[0], "stream_id"):
                    # Convert ZulipStream objects to dicts
                    return [
                        {
                            "id": (
                                stream.stream_id
                                if hasattr(stream, "stream_id")
                                else stream.get("id")
                            ),
                            "name": (
                                stream.name
                                if hasattr(stream, "name")
                                else stream.get("name")
                            ),
                            "description": (
                                stream.description
                                if hasattr(stream, "description")
                                else stream.get("description")
                            ),
                            "is_private": (
                                stream.is_private
                                if hasattr(stream, "is_private")
                                else stream.get("is_private")
                            ),
                        }
                        for stream in streams
                    ]
                return streams

            except ConnectionError as e:
                track_tool_error("get_streams", "ConnectionError")
                logger.error(f"Connection error in get_streams: {e}")
                return [{"error": f"Failed to retrieve streams: {str(e)}"}]
            except Exception as e:
                track_tool_error("get_streams", "Exception")
                logger.error(f"Error in get_streams: {e}")
                return [{"error": f"An unexpected error occurred: {str(e)}"}]


@mcp.tool()
def get_users() -> list[dict[str, Any]]:
    """Get list of all users in the Zulip organization."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_users"}):
        with LogContext(logger, tool="get_users"):
            track_tool_call("get_users")
            try:
                # Get user list
                client = get_client()
                users = client.get_users()

                # Handle both ZulipUser objects and dicts
                if users and hasattr(users[0], "user_id"):
                    # Convert ZulipUser objects to dicts
                    return [
                        {
                            "id": (
                                user.user_id
                                if hasattr(user, "user_id")
                                else user.get("id")
                            ),
                            "full_name": (
                                user.full_name
                                if hasattr(user, "full_name")
                                else user.get("full_name")
                            ),
                            "email": (
                                user.email
                                if hasattr(user, "email")
                                else user.get("email")
                            ),
                            "is_active": (
                                user.is_active
                                if hasattr(user, "is_active")
                                else user.get("is_active")
                            ),
                            "is_bot": (
                                user.is_bot
                                if hasattr(user, "is_bot")
                                else user.get("is_bot")
                            ),
                            "avatar_url": (
                                user.avatar_url
                                if hasattr(user, "avatar_url")
                                else user.get("avatar_url")
                            ),
                        }
                        for user in users
                    ]
                return users

            except ConnectionError as e:
                track_tool_error("get_users", "ConnectionError")
                logger.error(f"Connection error in get_users: {e}")
                return [{"error": f"Failed to retrieve users: {str(e)}"}]
            except Exception as e:
                track_tool_error("get_users", "Exception")
                logger.error(f"Error in get_users: {e}")
                return [{"error": f"An unexpected error occurred: {str(e)}"}]


@mcp.tool()
def add_reaction(message_id: int, emoji_name: str) -> dict[str, Any]:
    """Add an emoji reaction to a message.

    Args:
        message_id: ID of the message to react to
        emoji_name: Name of the emoji (e.g., 'thumbs_up')
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "add_reaction"}):
        with LogContext(
            logger, tool="add_reaction", message_id=message_id, emoji=emoji_name
        ):
            track_tool_call("add_reaction")
            try:
                # Validate inputs
                if message_id < 1:
                    return {"status": "error", "error": "Invalid message ID"}

                # Validate emoji
                from .security import validate_emoji

                if not validate_emoji(emoji_name):
                    return {"status": "error", "error": "Invalid emoji name"}

                # Add reaction
                client = get_client()
                result = client.add_reaction(message_id, emoji_name)

                if result.get("result") == "success":
                    return {"status": "success", "message": "Reaction added"}
                else:
                    return {
                        "status": "error",
                        "error": result.get("msg", "Unknown error"),
                    }

            except Exception as e:
                track_tool_error("add_reaction", "Exception")
                return create_error_response(e, "add_reaction")


@mcp.tool()
def edit_message(
    message_id: int, content: str | None = None, topic: str | None = None
) -> dict[str, Any]:
    """Edit an existing message's content or topic.

    Args:
        message_id: ID of the message to edit
        content: New message content (optional)
        topic: New topic name (optional)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "edit_message"}):
        with LogContext(logger, tool="edit_message", message_id=message_id):
            track_tool_call("edit_message")
            try:
                # Validate inputs
                if message_id < 1:
                    return {"status": "error", "error": "Invalid message ID"}
                if topic and not validate_topic(topic):
                    return {"status": "error", "error": f"Invalid topic: {topic}"}
                if not content and not topic:
                    return {
                        "status": "error",
                        "error": "Must provide content or topic to edit",
                    }

                # Sanitize content
                if content:
                    content = sanitize_input(content)

                # Edit message
                client = get_client()
                result = client.edit_message(message_id, content, topic)

                if result.get("result") == "success":
                    return {"status": "success", "message": "Message edited"}
                else:
                    return {
                        "status": "error",
                        "error": result.get("msg", "Unknown error"),
                    }

            except Exception as e:
                track_tool_error("edit_message", "Exception")
                return create_error_response(e, "edit_message")


@mcp.tool()
def get_daily_summary(
    stream_name: str | list[str] | None = None, hours_back: int = 24
) -> dict[str, Any]:
    """Generate a daily summary of messages from specified streams.

    Args:
        stream_name: Stream name, list of stream names, or None for all streams
        hours_back: Hours of history to summarize (default: 24)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_daily_summary"}):
        with LogContext(logger, tool="get_daily_summary", stream=str(stream_name)):
            track_tool_call("get_daily_summary")
            try:
                # Handle different input types
                streams_to_check = []
                if stream_name is None:
                    # Get all streams
                    streams_to_check = None
                elif isinstance(stream_name, str):
                    # Single stream
                    if not validate_stream_name(stream_name):
                        return {
                            "status": "error",
                            "error": f"Invalid stream name: {stream_name}",
                        }
                    streams_to_check = [stream_name]
                elif isinstance(stream_name, list):
                    # Multiple streams
                    for stream in stream_name:
                        if not validate_stream_name(stream):
                            return {
                                "status": "error",
                                "error": f"Invalid stream name: {stream}",
                            }
                    streams_to_check = stream_name
                else:
                    return {
                        "status": "error",
                        "error": f"Invalid stream_name type: {type(stream_name)}",
                    }
                if hours_back < 1 or hours_back > 168:  # Max 1 week
                    return {
                        "status": "error",
                        "error": "hours_back must be between 1 and 168",
                    }

                # Check if we should use client's get_daily_summary for multiple streams
                client = get_client()
                if hasattr(client, "get_daily_summary") and streams_to_check:
                    # Use client's method which handles multiple streams
                    summary_data = client.get_daily_summary(
                        streams_to_check, hours_back
                    )
                    return {
                        "status": "success",
                        "data": summary_data,
                        "period_hours": hours_back,
                    }

                # Fallback to manual summary generation
                all_messages = []
                if streams_to_check is None:
                    # Get messages from all streams
                    messages = get_messages(None, None, hours_back, 500)
                    all_messages.extend([m for m in messages if "error" not in m])
                else:
                    # Get messages from specific streams
                    for stream in streams_to_check:
                        messages = get_messages(stream, None, hours_back, 500)
                        all_messages.extend([m for m in messages if "error" not in m])

                if not all_messages:
                    return {
                        "status": "success",
                        "summary": "No messages found in the specified period.",
                        "period_hours": hours_back,
                        "stream": stream_name or "all streams",
                    }

                # Group messages by topic
                topics = {}
                for msg in all_messages:
                    topic = msg.get("topic", "No topic")
                    if topic not in topics:
                        topics[topic] = []
                    topics[topic].append(msg)

                # Create summary
                summary = {
                    "status": "success",
                    "period_hours": hours_back,
                    "stream": (
                        stream_name
                        if isinstance(stream_name, str)
                        else "multiple streams" if stream_name else "all streams"
                    ),
                    "total_messages": len(all_messages),
                    "topics_count": len(topics),
                    "topics": [
                        {
                            "name": topic,
                            "message_count": len(msgs),
                            "latest_message": msgs[-1].get("content", "")[:100],
                        }
                        for topic, msgs in sorted(
                            topics.items(), key=lambda x: len(x[1]), reverse=True
                        )[:10]
                    ],
                }

                return summary

            except Exception as e:
                track_tool_error("get_daily_summary", "Exception")
                logger.error(f"Error in get_daily_summary: {e}")
                return {"status": "error", "error": str(e)}


# Agent Communication Tools
@mcp.tool()
def register_agent(
    agent_name: str | None = None,
    agent_type: str = "claude_code",
    private_stream: bool = True,
    use_instance_identity: bool = True,
) -> dict[str, Any]:
    """Register an AI agent with dedicated Zulip communication channel.

    Automatically detects project context and creates unique identity per instance.

    Args:
        agent_name: Name of the agent (auto-generated if None)
        agent_type: Type of agent (claude_code, github_copilot, codeium, custom)
        private_stream: Whether to create a private stream
        use_instance_identity: Use smart instance detection for multi-project support

    Returns:
        Agent registration details including agent_id, stream_name, bot_name, instance_id
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "register_agent"}):
        with LogContext(logger, tool="register_agent", agent_name=agent_name):
            track_tool_call("register_agent")
            try:
                global config_manager
                from .instance_identity import get_instance_identity
                from .services.agent_registry import AgentRegistry

                # Use bot client if available for agent operations
                if config_manager is None:
                    from .config import ConfigManager

                    config_manager = ConfigManager()
                client = (
                    get_bot_client()
                    if config_manager.has_bot_credentials()
                    else get_client()
                )

                # Get instance identity for this Claude Code session
                if use_instance_identity:
                    instance = get_instance_identity()

                    # Use instance-aware naming
                    if not agent_name:
                        agent_name = instance.get_bot_name()

                    # Create registry with instance awareness
                    registry = AgentRegistry(config_manager, client)

                    # Register with instance metadata
                    result = registry.register_agent(
                        agent_name=agent_name,
                        agent_type=agent_type,
                        private_stream=private_stream,
                        metadata=instance.get_metadata(),
                    )

                    # Add instance info to result
                    if result.get("status") == "success":
                        result["instance"] = {
                            "instance_id": instance.get_instance_id(),
                            "session_id": instance.get_session_id(),
                            "display_name": instance.get_display_name(),
                            "stream_name": instance.get_stream_name(),
                        }

                        # Store both agent ID and instance ID for this session
                        agent_data = result.get("agent", {})
                        os.environ["CLAUDE_CODE_AGENT_ID"] = agent_data.get("id", "")
                        os.environ["CLAUDE_CODE_INSTANCE_ID"] = (
                            instance.get_instance_id()
                        )
                        os.environ["CLAUDE_CODE_SESSION_ID"] = instance.get_session_id()
                else:
                    # Traditional registration without instance identity
                    registry = AgentRegistry(config_manager, client)
                    result = registry.register_agent(
                        agent_name or "Claude Code", agent_type, private_stream
                    )

                    if result.get("status") == "success":
                        agent_data = result.get("agent", {})
                        os.environ["CLAUDE_CODE_AGENT_ID"] = agent_data.get("id", "")

                return result
            except Exception as e:
                track_tool_error("register_agent", "Exception")
                return create_error_response(e, "register_agent")


@mcp.tool()
def agent_message(
    agent_id: str,
    message_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a message from agent to human via Zulip.

    Args:
        agent_id: Unique agent identifier
        message_type: Type of message (status, question, completion, error)
        content: Message content
        metadata: Optional metadata (files, progress, duration)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "agent_message"}):
        with LogContext(logger, tool="agent_message", agent_id=agent_id):
            track_tool_call("agent_message")
            try:
                global config_manager
                from .tools.agent_communication import AgentCommunication

                if config_manager is None:
                    from .config import ConfigManager

                    config_manager = ConfigManager()
                client = (
                    get_bot_client()
                    if config_manager.has_bot_credentials()
                    else get_client()
                )
                comm = AgentCommunication(config_manager, client)
                return comm.agent_message(agent_id, message_type, content, metadata)  # type: ignore
            except Exception as e:
                track_tool_error("send_agent_status", "Exception")
                return create_error_response(e, "send_agent_status")


# Task Management Tools
@mcp.tool()
def start_task(
    agent_id: str,
    task_name: str,
    task_description: str,
    subtasks: list[str] | None = None,
) -> dict[str, Any]:
    """Notify user that agent is starting a new task.

    Args:
        agent_id: Unique agent identifier
        task_name: Name of the task
        task_description: Detailed description
        subtasks: Optional list of subtasks
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "start_task"}):
        with LogContext(logger, tool="start_task", agent_id=agent_id):
            track_tool_call("start_task")
            try:
                from .tools.task_tracking import TaskTracking

                tracker = TaskTracking(config_manager, get_client())  # type: ignore
                return tracker.start_task(
                    agent_id, task_name, task_description, subtasks
                )
            except Exception as e:
                track_tool_error("start_task", "Exception")
                return create_error_response(e, "start_task")


@mcp.tool()
def update_task_progress(
    task_id: str,
    subtask_completed: str | None = None,
    progress_percentage: int | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Update task progress in real-time.

    Args:
        task_id: Task identifier
        subtask_completed: Optional completed subtask name
        progress_percentage: Optional progress (0-100)
        blockers: Optional list of blockers
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "update_task_progress"}):
        with LogContext(logger, tool="update_task_progress", task_id=task_id):
            track_tool_call("update_task_progress")
            try:
                from .tools.task_tracking import TaskTracking

                tracker = TaskTracking(config_manager, get_client())  # type: ignore
                return tracker.update_task_progress(
                    task_id, subtask_completed, progress_percentage, blockers
                )
            except Exception as e:
                track_tool_error("update_task_progress", "Exception")
                return create_error_response(e, "update_task_progress")


@mcp.tool()
def complete_task(
    task_id: str,
    summary: str,
    outputs: dict[str, Any],
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark task as complete with detailed summary.

    Args:
        task_id: Task identifier
        summary: Task completion summary
        outputs: Task outputs (files_created, files_modified, etc.)
        metrics: Optional metrics (time_taken, test_coverage, etc.)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "complete_task"}):
        with LogContext(logger, tool="complete_task", task_id=task_id):
            track_tool_call("complete_task")
            try:
                from .tools.task_tracking import TaskTracking

                tracker = TaskTracking(config_manager, get_client())  # type: ignore
                return tracker.complete_task(task_id, summary, outputs, metrics)
            except Exception as e:
                track_tool_error("complete_task", "Exception")
                return create_error_response(e, "complete_task")


# Instance Management Tools
@mcp.tool()
def list_instances() -> dict[str, Any]:
    """List all active Claude Code instances across projects and machines.

    Returns information about each instance including project, branch, hostname, and last seen time.
    """
    try:
        from .instance_identity import get_instance_identity

        instance = get_instance_identity()
        instances = instance.list_all_instances()

        result = []
        for inst_id, inst_data in instances.items():
            result.append(
                {
                    "instance_id": inst_id,
                    "session_id": inst_data.get("session_id"),
                    "project": inst_data.get("project", {}).get("name"),
                    "branch": inst_data.get("project", {}).get("git_branch"),
                    "hostname": inst_data.get("machine", {}).get("hostname"),
                    "user": inst_data.get("machine", {}).get("user"),
                    "last_seen": inst_data.get("last_seen"),
                    "stream": inst_data.get("stream_name"),
                    "bot_name": inst_data.get("bot_name"),
                }
            )

        return {
            "status": "success",
            "instances": result,
            "count": len(result),
            "current_instance": instance.get_instance_id(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def cleanup_old_instances(days: int = 30) -> dict[str, Any]:
    """Remove instances not seen in specified number of days.

    Args:
        days: Number of days of inactivity before removal (default: 30)
    """
    try:
        from .instance_identity import get_instance_identity

        instance = get_instance_identity()
        removed = instance.cleanup_old_instances(days)

        return {
            "status": "success",
            "removed": removed,
            "message": f"Removed {removed} inactive instances older than {days} days",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Stream Management Tools
@mcp.tool()
def create_stream(
    name: str,
    description: str,
    is_private: bool = False,
    is_announcement_only: bool = False,
) -> dict[str, Any]:
    """Create a new stream with configuration.

    Args:
        name: Stream name
        description: Stream description
        is_private: Whether stream is private
        is_announcement_only: Whether only admins can post
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "create_stream"}):
        with LogContext(logger, tool="create_stream", name=name):
            track_tool_call("create_stream")
            try:
                from .tools.stream_management import StreamManagement

                mgmt = StreamManagement(config_manager, get_client())  # type: ignore
                return mgmt.create_stream(
                    name, description, is_private, is_announcement_only
                )
            except Exception as e:
                track_tool_error("create_stream", "Exception")
                return create_error_response(e, "create_stream")


@mcp.tool()
def rename_stream(stream_id: int, new_name: str) -> dict[str, Any]:
    """Rename an existing stream.

    Args:
        stream_id: Stream ID to rename
        new_name: New stream name
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "rename_stream"}):
        with LogContext(logger, tool="rename_stream", stream_id=stream_id):
            track_tool_call("rename_stream")
            try:
                from .tools.stream_management import StreamManagement

                mgmt = StreamManagement(config_manager, get_client())  # type: ignore
                return mgmt.rename_stream(stream_id, new_name)
            except Exception as e:
                track_tool_error("rename_stream", "Exception")
                return create_error_response(e, "rename_stream")


@mcp.tool()
def archive_stream(stream_id: int, message: str | None = None) -> dict[str, Any]:
    """Archive a stream with optional farewell message.

    Args:
        stream_id: Stream ID to archive
        message: Optional farewell message
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "archive_stream"}):
        with LogContext(logger, tool="archive_stream", stream_id=stream_id):
            track_tool_call("archive_stream")
            try:
                from .tools.stream_management import StreamManagement

                mgmt = StreamManagement(config_manager, get_client())  # type: ignore
                return mgmt.archive_stream(stream_id, message)
            except Exception as e:
                track_tool_error("archive_stream", "Exception")
                return create_error_response(e, "archive_stream")


@mcp.tool()
def wait_for_response(
    agent_id: str, request_id: str, timeout: int = 300
) -> dict[str, Any]:
    """Wait for user response to an input request.

    Args:
        agent_id: Agent ID
        request_id: Request ID to wait for
        timeout: Timeout in seconds

    Returns:
        Response from user or None if timeout
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "wait_for_response"}):
        with LogContext(logger, tool="wait_for_response", agent_id=agent_id):
            track_tool_call("wait_for_response")
            try:
                from .tools.agent_communication import AgentCommunication

                comm = AgentCommunication(config_manager, get_client())  # type: ignore
                response = comm.wait_for_response(agent_id, request_id, timeout)

                if response:
                    return {"status": "success", "response": response}
                else:
                    return {
                        "status": "timeout",
                        "message": "No response received within timeout period",
                    }
            except Exception as e:
                track_tool_error("wait_for_response", "Exception")
                return create_error_response(e, "wait_for_response")


@mcp.tool()
def organize_streams_by_project(
    project_mapping: dict[str, list[str]],
) -> dict[str, Any]:
    """Organize streams by project prefix.

    Args:
        project_mapping: Dictionary mapping project names to stream patterns

    Example:
        {"IOWarp": ["IOWarp-dev", "IOWarp-support"]}
    """
    with Timer(
        "zulip_mcp_tool_duration_seconds", {"tool": "organize_streams_by_project"}
    ):
        with LogContext(logger, tool="organize_streams_by_project"):
            track_tool_call("organize_streams_by_project")
            try:
                from .tools.stream_management import StreamManagement

                mgmt = StreamManagement(config_manager, get_client())  # type: ignore
                return mgmt.organize_streams_by_project(project_mapping)
            except Exception as e:
                track_tool_error("organize_streams_by_project", "Exception")
                return create_error_response(e, "organize_streams_by_project")


# Health and monitoring endpoints
@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Perform comprehensive health check of the MCP server.

    Returns detailed health status including:
    - Overall system health
    - Individual component status
    - Performance metrics
    - Configuration validation
    """
    try:
        from .health import perform_health_check

        return await perform_health_check()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@mcp.tool()
def readiness_check() -> dict[str, Any]:
    """Check if the MCP server is ready to accept requests.

    This is used by load balancers and orchestration systems
    to determine if the service should receive traffic.
    """
    try:
        from .health import get_readiness

        return get_readiness()
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "ready": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@mcp.tool()
def get_metrics() -> dict[str, Any]:
    """Get Prometheus-compatible metrics for monitoring.

    Returns metrics data including:
    - Request counts and durations
    - Cache hit/miss ratios
    - Error rates
    - System performance indicators
    """
    try:
        from .metrics import metrics

        return metrics.get_metrics()
    except Exception as e:
        logger.error(f"Metrics retrieval failed: {e}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}


# MCP Resources
@mcp.resource("zulip://stream/{stream_name}")
def get_stream_messages(stream_name: str) -> list[Any]:
    """Get messages from a specific stream as a resource."""
    from mcp.types import TextContent

    # Validate stream name
    if not validate_stream_name(stream_name):
        return [TextContent(type="text", text=f"Invalid stream name: {stream_name}")]

    try:
        messages = get_messages(stream_name, limit=100)

        # Format messages as text content
        content_lines = [f"Messages from #{stream_name}\n" + "=" * 40]

        for msg in messages[:50]:  # Limit to 50 messages for resource
            if "error" not in msg:
                timestamp = datetime.fromtimestamp(msg.get("timestamp", 0)).strftime(
                    "%Y-%m-%d %H:%M"
                )
                sender = msg.get("sender", "Unknown")
                topic = msg.get("topic", "No topic")
                content = msg.get("content", "")[:200]  # Truncate long messages

                content_lines.append(f"\n[{timestamp}] {sender} in {topic}:")
                content_lines.append(f"  {content}")

        return [TextContent(type="text", text="\n".join(content_lines))]

    except Exception as e:
        logger.error(f"Error in get_stream_messages resource: {e}")
        return [TextContent(type="text", text=f"Error retrieving messages: {str(e)}")]


@mcp.resource("zulip://streams")
def list_streams() -> list[Any]:
    """List all available Zulip streams as a resource."""
    from mcp.types import TextContent

    try:
        streams = get_streams()

        # Format streams as text content
        content_lines = ["Available Zulip Streams", "=" * 40]

        public_streams = []
        private_streams = []

        for stream in streams:
            if "error" not in stream:
                if stream.get("is_private"):
                    private_streams.append(stream)
                else:
                    public_streams.append(stream)

        if public_streams:
            content_lines.append("\n📢 Public Streams:")
            for stream in public_streams:
                content_lines.append(
                    f"  • {stream.get('name')} - {stream.get('description', 'No description')}"
                )

        if private_streams:
            content_lines.append("\n🔒 Private Streams:")
            for stream in private_streams:
                content_lines.append(
                    f"  • {stream.get('name')} - {stream.get('description', 'No description')}"
                )

        return [TextContent(type="text", text="\n".join(content_lines))]

    except Exception as e:
        logger.error(f"Error in list_streams resource: {e}")
        return [TextContent(type="text", text=f"Error retrieving streams: {str(e)}")]


@mcp.resource("zulip://users")
def list_users() -> list[Any]:
    """List all users in the Zulip organization as a resource."""
    from mcp.types import TextContent

    try:
        users = get_users()

        # Format users as text content
        active_users = []
        bots = []
        inactive = []

        for user in users:
            if "error" not in user:
                if user.get("is_bot"):
                    bots.append(user)
                elif user.get("is_active"):
                    active_users.append(user)
                else:
                    inactive.append(user)

        content_lines = ["Zulip Users", "=" * 40]

        if active_users:
            content_lines.append(f"\nActive Users ({len(active_users)}):")
            for user in active_users[:50]:  # Limit display
                content_lines.append(
                    f"  • {user.get('full_name')} ({user.get('email')})"
                )

        if bots:
            content_lines.append(f"\nBots ({len(bots)}):")
            for bot in bots[:20]:  # Limit display
                content_lines.append(f"  • {bot.get('full_name')} ({bot.get('email')})")

        if inactive:
            content_lines.append(f"\nInactive Users: {len(inactive)}")

        return [TextContent(type="text", text="\n".join(content_lines))]

    except Exception as e:
        logger.error(f"Error in list_users resource: {e}")
        return [TextContent(type="text", text=f"Error retrieving users: {str(e)}")]


# MCP Prompts
@mcp.prompt("daily_summary")
def daily_summary_prompt(
    streams: list[str] | str | None = None, hours: int = 24
) -> list[Any]:
    """Generate a daily summary prompt for messages."""
    try:
        client = get_client()
        # Handle different input types
        stream_list = None
        if isinstance(streams, str):
            stream_list = [streams]
        elif isinstance(streams, list):
            stream_list = streams
        summary = client.get_daily_summary(stream_list, hours_back=hours)

        prompt_lines = ["# Zulip Daily Summary", ""]
        prompt_lines.append(f"**Total Messages**: {summary.get('total_messages', 0)}")
        prompt_lines.append(
            f"**Time Range**: {summary.get('time_range', 'Last 24 hours')}"
        )

        if summary.get("streams"):
            prompt_lines.append("\nStream Activity:")
            for stream, data in summary["streams"].items():
                prompt_lines.append(f"  • {stream}: {data['message_count']} messages")
                if data.get("topics"):
                    top_topics = sorted(
                        data["topics"].items(), key=lambda x: x[1], reverse=True
                    )[:3]
                    for topic, count in top_topics:
                        prompt_lines.append(f"    - {topic}: {count} messages")

        if summary.get("top_senders"):
            prompt_lines.append("\n## Most Active Users")
            for sender, count in list(summary["top_senders"].items())[:5]:
                prompt_lines.append(f"  • {sender}: {count} messages")

        from mcp.types import TextContent

        return [TextContent(type="text", text="\n".join(prompt_lines))]

    except Exception as e:
        logger.error(f"Error in daily_summary_prompt: {e}")
        from mcp.types import TextContent

        return [TextContent(type="text", text=f"Error generating summary: {str(e)}")]


@mcp.prompt("morning_briefing")
def morning_briefing_prompt(streams: list[str] | str | None = None) -> list[Any]:
    """Generate a morning briefing with overnight activity."""
    try:
        client = get_client()

        # Get yesterday's activity (24 hours) and this week's data
        yesterday_summary = client.get_daily_summary(
            streams if isinstance(streams, list) else [streams] if streams else None,
            hours_back=24,
        )
        week_summary = client.get_daily_summary(
            streams if isinstance(streams, list) else [streams] if streams else None,
            hours_back=168,
        )

        prompt_lines = ["# Good Morning!", ""]

        # Yesterday's activity
        prompt_lines.append("## Yesterday's Activity")
        prompt_lines.append(
            f"Total messages: {yesterday_summary.get('total_messages', 0)}"
        )

        if yesterday_summary.get("top_senders"):
            top_sender = list(yesterday_summary["top_senders"].items())[0]
            prompt_lines.append(
                f"Most active: {top_sender[0]} ({top_sender[1]} messages)"
            )

        # This week's summary
        prompt_lines.append("\n## This Week")
        prompt_lines.append(f"Total messages: {week_summary.get('total_messages', 0)}")

        # Most active streams
        if week_summary.get("streams"):
            prompt_lines.append("\n## Most Active Streams")
            for stream, data in list(week_summary["streams"].items())[:3]:
                prompt_lines.append(f"  • {stream}: {data['message_count']} messages")
                if data.get("topics"):
                    top_topic = (
                        list(data["topics"].items())[0] if data["topics"] else None
                    )
                    if top_topic:
                        prompt_lines.append(
                            f"    Top topic: {top_topic[0]} ({top_topic[1]} messages)"
                        )

        from mcp.types import TextContent

        return [TextContent(type="text", text="\n".join(prompt_lines))]

    except Exception as e:
        logger.error(f"Error in morning_briefing_prompt: {e}")
        from mcp.types import TextContent

        return [TextContent(type="text", text=f"Error generating briefing: {str(e)}")]


@mcp.prompt("catch_up")
def catch_up_prompt(
    stream_name: str | list[str] | None = None, hours: int = 24
) -> list[Any]:
    """Generate a catch-up prompt for missed messages."""
    from mcp.types import TextContent

    # Validate hours before any other operations
    if hours < 1 or hours > 24:
        return [TextContent(type="text", text="Error: hours must be between 1 and 24")]

    try:
        client = get_client()

        prompt_lines = ["# Quick Catch-Up", ""]
        prompt_lines.append(f"**Period**: Last {hours} hours")

        # Get streams if not specified
        if stream_name is None:
            streams = client.get_streams()
            # Get messages from each stream
            total_messages = 0
            stream_activity = []

            all_topics = {}
            all_senders = set()

            for stream in streams[:5]:  # Limit to top 5 streams
                stream_name_str = (
                    stream.name if hasattr(stream, "name") else stream.get("name", "")
                )
                messages = client.get_messages_from_stream(
                    stream_name_str, None, hours, 50
                )
                if messages:
                    total_messages += len(messages)
                    stream_activity.append((stream_name_str, len(messages)))

                    # Collect topics and senders
                    for msg in messages:
                        topic = msg.get("topic") or msg.get("subject", "No topic")
                        sender = msg.get("sender", "Unknown")
                        all_senders.add(sender)

                        if topic not in all_topics:
                            all_topics[topic] = 0
                        all_topics[topic] += 1

            prompt_lines.append(f"\n**Total messages**: {total_messages}")

            if stream_activity:
                prompt_lines.append("\n## Active Streams:")
                for name, count in stream_activity:
                    if count > 0:
                        prompt_lines.append(f"  • {name}: {count} messages")

            # Add top topics
            if all_topics:
                top_topics = sorted(
                    all_topics.items(), key=lambda x: x[1], reverse=True
                )[:5]
                prompt_lines.append("\n## Active Topics:")
                for topic, count in top_topics:
                    prompt_lines.append(f"  • {topic}: {count} messages")

            # Add active participants
            if all_senders:
                prompt_lines.append("\n## Active Participants:")
                for sender in list(all_senders)[:10]:  # Limit to 10 senders
                    prompt_lines.append(f"  • {sender}")
        else:
            # Get messages from specific stream(s)
            summary = get_daily_summary(stream_name, hours_back=hours)

            if summary.get("status") == "success":
                prompt_lines.append(
                    f"Total messages: {summary.get('total_messages', 0)}"
                )
                prompt_lines.append(f"Active topics: {summary.get('topics_count', 0)}")

                if summary.get("topics"):
                    prompt_lines.append("\nKey Discussions:")
                    for topic_data in summary["topics"]:
                        prompt_lines.append(
                            f"  • {topic_data['name']}: {topic_data['message_count']} messages"
                        )

        prompt_lines.append("\nUse 'get_messages' to read specific topics in detail.")

        return [TextContent(type="text", text="\n".join(prompt_lines))]

    except Exception as e:
        logger.error(f"Error in catch_up_prompt: {e}")
        return [TextContent(type="text", text=f"Error generating catch-up: {str(e)}")]


def main() -> None:
    """Main entry point for the MCP server."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Start the MCP server directly
    mcp.run()


if __name__ == "__main__":
    main()
