"""Enhanced MCP server for Zulip integration with security and error handling."""

import logging
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ConfigManager
from .exceptions import ConnectionError, create_error_response

# Import structured logging
from .logging_config import LogContext, get_logger, setup_structured_logging

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
                async with MessageScheduler(config_manager.config) as scheduler:
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
                global config_manager
                if config_manager is None:
                    config_manager = ConfigManager()
                async with MessageScheduler(config_manager.config) as scheduler:
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
                global config_manager
                if config_manager is None:
                    config_manager = ConfigManager()
                async with MessageScheduler(config_manager.config) as scheduler:
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
    if limit < 1 or limit > 1000:  # Increased limit for more flexibility
        return [{"error": "limit must be between 1 and 1000"}]

    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_messages"}):
        with LogContext(logger, tool="get_messages", stream=stream_name):
            track_tool_call("get_messages")
            try:
                client = get_client()

                if stream_name is None and topic is None:
                    messages = client.get_messages(num_before=limit)
                else:
                    messages = client.get_messages_from_stream(
                        stream_name, topic, hours_back, limit
                    )

                return [m.model_dump() for m in messages]

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
                if not query or not query.strip():
                    return [{"error": "Query cannot be empty"}]
                if limit < 1 or limit > 1000:
                    return [{"error": "limit must be between 1 and 1000"}]

                query = sanitize_input(query)
                client = get_client()
                results = client.search_messages(query, num_results=limit)
                return [r.model_dump() for r in results]

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
                client = get_client()
                streams = client.get_streams()
                return [s.model_dump() for s in streams]

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
                client = get_client()
                users = client.get_users()
                return [u.model_dump() for u in users]

            except ConnectionError as e:
                track_tool_error("get_users", "ConnectionError")
                logger.error(f"Connection error in get_users: {e}")
                return [{"error": f"Failed to retrieve users: {str(e)}"}]
            except Exception as e:
                track_tool_error("get_users", "Exception")
                logger.error(f"Error in get_users: {e}")
                return [{"error": f"An unexpected error occurred: {str(e)}"}]


@mcp.tool()
def create_stream(
    name: str,
    description: str,
    is_private: bool = False,
    is_announcement_only: bool = False,
) -> dict[str, Any]:
    """Create a new Zulip stream.

    Args:
        name: Name of the stream to create
        description: Description of the stream
        is_private: Whether the stream should be private (invite-only)
        is_announcement_only: Whether the stream should be announcement-only

    Returns:
        Result of stream creation operation
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "create_stream"}):
        with LogContext(logger, tool="create_stream", stream_name=name):
            track_tool_call("create_stream")
            try:
                # Validate inputs
                if not validate_stream_name(name):
                    return {"status": "error", "error": f"Invalid stream name: {name}"}

                # Sanitize inputs
                name = sanitize_input(name)
                description = sanitize_input(description)

                # Get client and config
                client = get_client()
                global config_manager
                if config_manager is None:
                    from .config import ConfigManager

                    config_manager = ConfigManager()

                # Import and use stream management
                from .tools.stream_management import StreamManagement

                stream_manager = StreamManagement(config_manager, client)

                result = stream_manager.create_stream(
                    name=name,
                    description=description,
                    is_private=is_private,
                    is_announcement_only=is_announcement_only,
                )

                if result.get("status") == "success":
                    return result
                else:
                    return result

            except Exception as e:
                track_tool_error("create_stream", "Exception")
                logger.error(f"Error in create_stream: {e}")
                return {"status": "error", "error": str(e)}


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
                client = get_client()
                streams_to_check = []
                if stream_name is None:
                    all_streams = client.get_streams()
                    streams_to_check = [s.name for s in all_streams if not s.is_private]
                elif isinstance(stream_name, str):
                    if not validate_stream_name(stream_name):
                        return {
                            "status": "error",
                            "error": f"Invalid stream name: {stream_name}",
                        }
                    streams_to_check = [stream_name]
                elif isinstance(stream_name, list):
                    for stream in stream_name:
                        if not validate_stream_name(stream):
                            return {
                                "status": "error",
                                "error": f"Invalid stream name: {stream}",
                            }
                    streams_to_check = stream_name

                if hours_back < 1 or hours_back > 168:  # Max 1 week
                    return {
                        "status": "error",
                        "error": "hours_back must be between 1 and 168",
                    }

                summary_data = client.get_daily_summary(streams_to_check, hours_back)
                return {
                    "status": "success",
                    "data": summary_data,
                    "period_hours": hours_back,
                }

            except Exception as e:
                track_tool_error("get_daily_summary", "Exception")
                logger.error(f"Error in get_daily_summary: {e}")
                return {"status": "error", "error": str(e)}


@mcp.tool()
def agent_message(
    content: str,
    agent_type: str = "claude-code",
    force_send: bool = False,
    require_response: bool = False,
) -> dict[str, Any]:
    """
    Sends a message to the Agents-Channel with automatic topic routing.

    Messages are routed to topics like: agent_type/date/session_id
    Only sends when AFK mode is enabled unless force_send is True.

    Args:
        content: The content of the message.
        agent_type: Type of agent (claude-code, gemini, cursor, etc.)
        force_send: Send even if AFK is disabled (for important messages)
        require_response: Whether to wait for a user response

    Returns:
        A dictionary with the status of the message sending operation.
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "agent_message"}):
        with LogContext(logger, tool="agent_message", agent_type=agent_type):
            track_tool_call("agent_message")
            try:
                from .agent_tracker import AgentTracker

                tracker = AgentTracker()

                # Get formatted message with routing info
                msg_info = tracker.format_agent_message(
                    content, agent_type, require_response
                )

                # Check if we should send
                if msg_info["status"] == "skipped" and not force_send:
                    return msg_info

                # If force_send, get the routing info even if AFK is disabled
                if force_send and msg_info["status"] == "skipped":
                    reg_info = tracker.register_agent(agent_type)
                    msg_info = {
                        "status": "ready",
                        "stream": reg_info["stream"],
                        "topic": reg_info["topic"],
                        "content": content,
                        "response_id": None,
                    }

                # Get client with bot identity if available
                client = get_bot_client()

                # Check if Agents-Channel exists
                streams = client.get_streams()
                stream_exists = any(s.name == msg_info["stream"] for s in streams)

                if not stream_exists:
                    return {
                        "status": "error",
                        "error": f"Stream '{msg_info['stream']}' does not exist. Please run setup script or create manually.",
                    }

                result = client.send_message(
                    message_type="stream",
                    to=msg_info["stream"],
                    content=msg_info["content"],
                    topic=msg_info["topic"],
                )

                if result.get("result") == "success":
                    track_message_sent("stream")
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

            except Exception as e:
                track_tool_error("agent_message", "Exception")
                return create_error_response(e, "agent_message")


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


@mcp.tool()
def rename_stream(stream_id: int, new_name: str) -> dict[str, Any]:
    """Rename an existing Zulip stream.

    Args:
        stream_id: The ID of the stream to rename
        new_name: The new name for the stream
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "rename_stream"}):
        track_tool_call("rename_stream")
        try:
            from .tools.stream_management import StreamManagement

            client = get_client()
            stream_mgmt = StreamManagement(config_manager, client)
            return stream_mgmt.rename_stream(stream_id, new_name)
        except Exception as e:
            track_tool_error("rename_stream", "Exception")
            logger.error(f"Failed to rename stream: {e}")
            return {"status": "error", "error": str(e)}


@mcp.tool()
def archive_stream(
    stream_id: int, farewell_message: str | None = None
) -> dict[str, Any]:
    """Archive a Zulip stream with optional farewell message.

    Args:
        stream_id: The ID of the stream to archive
        farewell_message: Optional message to post before archiving
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "archive_stream"}):
        track_tool_call("archive_stream")
        try:
            from .tools.stream_management import StreamManagement

            client = get_client()
            stream_mgmt = StreamManagement(config_manager, client)
            return stream_mgmt.archive_stream(stream_id, farewell_message)
        except Exception as e:
            track_tool_error("archive_stream", "Exception")
            logger.error(f"Failed to archive stream: {e}")
            return {"status": "error", "error": str(e)}


@mcp.tool()
def wait_for_response(response_id: str, timeout_minutes: int = 5) -> dict[str, Any]:
    """Wait for a user response to a previous message.

    When you send a message with require_response=True, use this to wait for the reply.
    The user should reply with: @response [response_id] [their message]

    Args:
        response_id: The response ID from the agent_message call
        timeout_minutes: How long to wait (max 30 minutes)

    Returns:
        The user's response or timeout status
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "wait_for_response"}):
        track_tool_call("wait_for_response")
        try:
            import time

            from .agent_tracker import AgentTracker

            tracker = AgentTracker()
            timeout_minutes = min(timeout_minutes, 30)
            timeout_seconds = timeout_minutes * 60
            check_interval = 5  # Check every 5 seconds
            elapsed = 0

            while elapsed < timeout_seconds:
                # Check for response
                response = tracker.check_for_response(response_id)
                if response:
                    return {
                        "status": "success",
                        "response": response["response"],
                        "responded_at": response.get("responded_at"),
                        "wait_time_seconds": elapsed,
                    }

                # Wait before next check
                time.sleep(check_interval)
                elapsed += check_interval

            # Timeout reached
            return {
                "status": "timeout",
                "message": f"No response received after {timeout_minutes} minutes",
                "response_id": response_id,
            }

        except Exception as e:
            track_tool_error("wait_for_response", "Exception")
            logger.error(f"Failed to wait for response: {e}")
            return {"status": "error", "error": str(e)}


@mcp.tool()
def register_agent(agent_type: str = "claude-code") -> dict[str, Any]:
    """Register an AI agent and get its assigned topic in Agents-Channel.

    Registers the agent with automatic session tracking and returns
    the topic structure: agent_type/date/session_id

    Args:
        agent_type: Type of agent (claude-code, gemini, cursor, etc.)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "register_agent"}):
        track_tool_call("register_agent")
        try:
            from .agent_tracker import AgentTracker

            tracker = AgentTracker()

            reg_info = tracker.register_agent(agent_type)

            # Check if Agents-Channel exists
            client = get_client()
            streams = client.get_streams()
            stream_exists = any(s.name == reg_info["stream"] for s in streams)

            if not stream_exists:
                reg_info["warning"] = (
                    f"Stream '{reg_info['stream']}' does not exist. Please run setup or create manually."
                )

            return reg_info
        except Exception as e:
            track_tool_error("register_agent", "Exception")
            logger.error(f"Failed to register agent: {e}")
            return {"status": "error", "error": str(e)}


@mcp.tool()
def list_active_agents(hours: int = 24) -> dict[str, Any]:
    """List all agents that have been active recently.

    Args:
        hours: How many hours back to look (default 24, max 168/1 week)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "list_active_agents"}):
        track_tool_call("list_active_agents")
        try:
            from .agent_tracker import AgentTracker

            tracker = AgentTracker()

            hours = min(hours, 168)  # Max 1 week
            agents = tracker.get_active_agents(hours)

            return {
                "status": "success",
                "count": len(agents),
                "agents": agents,
                "period_hours": hours,
            }
        except Exception as e:
            logger.error(f"Failed to list active agents: {e}")
            return {"status": "error", "error": str(e)}


@mcp.tool()
def get_stream_topics(stream_id: int, include_archived: bool = False) -> dict[str, Any]:
    """Get all topics in a Zulip stream.

    Args:
        stream_id: The ID of the stream
        include_archived: Whether to include archived topics
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_stream_topics"}):
        track_tool_call("get_stream_topics")
        try:
            from .tools.stream_management import StreamManagement

            client = get_client()
            stream_mgmt = StreamManagement(config_manager, client)
            return stream_mgmt.get_stream_topics(stream_id, include_archived)
        except Exception as e:
            track_tool_error("get_stream_topics", "Exception")
            logger.error(f"Failed to get stream topics: {e}")
            return {"status": "error", "error": str(e)}


# MCP Resources
@mcp.resource("zulip://stream/{stream_name}")
def get_stream_messages(stream_name: str) -> list[Any]:
    """Get messages from a specific stream as a resource."""
    from mcp.types import TextContent

    if not validate_stream_name(stream_name):
        return [TextContent(type="text", text=f"Invalid stream name: {stream_name}")]

    try:
        client = get_client()
        messages = client.get_messages_from_stream(stream_name, limit=100)

        content_lines = [f"Messages from #{stream_name}\n" + "=" * 40]

        for msg in messages[:50]:  # Limit to 50 messages for resource
            timestamp = datetime.fromtimestamp(msg.timestamp).strftime("%Y-%m-%d %H:%M")
            sender = msg.sender_full_name
            topic = msg.subject or "No topic"
            content = msg.content[:200]  # Truncate long messages

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
        client = get_client()
        streams = client.get_streams()

        content_lines = ["Available Zulip Streams", "=" * 40]

        public_streams = [s for s in streams if not s.is_private]
        private_streams = [s for s in streams if s.is_private]

        if public_streams:
            content_lines.append("\n📢 Public Streams:")
            for stream in public_streams:
                content_lines.append(
                    f"  • {stream.name} - {stream.description or 'No description'}"
                )

        if private_streams:
            content_lines.append("\n🔒 Private Streams:")
            for stream in private_streams:
                content_lines.append(
                    f"  • {stream.name} - {stream.description or 'No description'}"
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
        client = get_client()
        users = client.get_users()

        active_users = [u for u in users if u.is_active and not u.is_bot]
        bots = [u for u in users if u.is_bot]
        inactive = [u for u in users if not u.is_active]

        content_lines = ["Zulip Users", "=" * 40]

        if active_users:
            content_lines.append(f"\nActive Users ({len(active_users)}):")
            for user in active_users[:50]:  # Limit display
                content_lines.append(f"  • {user.full_name} ({user.email})")

        if bots:
            content_lines.append(f"\nBots ({len(bots)}):")
            for bot in bots[:20]:  # Limit display
                content_lines.append(f"  • {bot.full_name} ({bot.email})")

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
