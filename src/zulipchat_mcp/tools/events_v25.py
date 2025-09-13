"""Consolidated event streaming tools for ZulipChat MCP v2.5.0.

This module implements the 3 stateless event streaming tools according to PLAN-REFACTOR.md:
1. register_events() - Register for real-time events without persistence
2. get_events() - Poll events from queue (stateless)
3. listen_events() - Simple event listener with callback support

NEW CAPABILITY: Real-time events without complex queue management

Features:
- IdentityManager integration for user/bot switching
- ParameterValidator for progressive disclosure
- ErrorHandler for comprehensive retry logic
- Stateless event handling without database persistence
- Support for webhooks and callback URLs
- Auto-cleanup of event queues
- Long-polling support
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from ..config import ConfigManager
from ..core.error_handling import get_error_handler
from ..core.identity import IdentityManager
from ..core.validation import NarrowFilter, ParameterValidator
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error

logger = get_logger(__name__)

# Response type definitions
EventQueue = dict[str, Any]
EventBatch = dict[str, Any]
Event = dict[str, Any]

# Event type definitions
EventType = Literal[
    "message",
    "subscription",
    "realm_user",
    "realm_emoji",
    "realm_filters",
    "realm_domains",
    "realm_bot",
    "stream",
    "default_streams",
    "default_stream_groups",
    "user_group",
    "user_status",
    "reaction",
    "presence",
    "typing",
    "heartbeat",
    "realm_linkifiers",
    "realm_playbooks",
    "alert_words",
    "custom_profile_fields",
    "muted_topics",
    "muted_users",
    "user_settings",
]

# Global instances
_config_manager: ConfigManager | None = None
_identity_manager: IdentityManager | None = None
_parameter_validator: ParameterValidator | None = None
_error_handler = get_error_handler()

# Active event queues for cleanup tracking
_active_queues: dict[str, dict[str, Any]] = {}


def _get_managers() -> tuple[ConfigManager, IdentityManager, ParameterValidator]:
    """Get or create manager instances."""
    global _config_manager, _identity_manager, _parameter_validator

    if _config_manager is None:
        _config_manager = ConfigManager()

    if _identity_manager is None:
        _identity_manager = IdentityManager(_config_manager)

    if _parameter_validator is None:
        _parameter_validator = ParameterValidator()

    return _config_manager, _identity_manager, _parameter_validator


def _convert_narrow_to_api_format(
    narrow: list[NarrowFilter | dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert narrow filters to Zulip API format."""
    result = []
    for item in narrow:
        if isinstance(item, NarrowFilter):
            result.append(item.to_dict())
        elif isinstance(item, dict):
            # Already in API format
            result.append(item)
        else:
            logger.warning(f"Unknown narrow filter type: {type(item)}")
    return result


async def register_events(
    event_types: list[EventType],
    narrow: list[NarrowFilter | dict[str, Any]] | None = None,
    all_public_streams: bool = False,
    # Stateless parameters - no DB persistence
    queue_lifespan_secs: int = 300,  # Auto-cleanup
    fetch_event_types: list[str] | None = None,  # Initial state
    client_capabilities: dict[str, Any] | None = None,
    # Expert parameters
    slim_presence: bool = False,
    include_subscribers: bool = False,
    client_gravatar: bool = False,
) -> EventQueue:
    """Register for real-time events without persistence.

    NEW CAPABILITY: Stateless event registration with auto-cleanup

    Args:
        event_types: Types of events to register for
        narrow: Message filters (only applies to message events)
        all_public_streams: Subscribe to all public streams
        queue_lifespan_secs: Automatic queue cleanup time (max 600 seconds)
        fetch_event_types: Event types to fetch initial state for
        client_capabilities: Client capability declarations
        slim_presence: Use slim presence format
        include_subscribers: Include subscriber lists in stream events
        client_gravatar: Include gravatar URLs

    Returns:
        Dictionary with queue information and initial state

    Raises:
        ValidationError: If parameters are invalid
        PermissionError: If user lacks required permissions
        ZulipMCPError: If Zulip API call fails
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "register_events"}):
        with LogContext(logger, tool="register_events", event_types=event_types):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "event_types": event_types,
                    "narrow": narrow,
                    "all_public_streams": all_public_streams,
                    "queue_lifespan_secs": queue_lifespan_secs,
                    "fetch_event_types": fetch_event_types,
                    "client_capabilities": client_capabilities,
                    "slim_presence": slim_presence,
                    "include_subscribers": include_subscribers,
                    "client_gravatar": client_gravatar,
                }

                # Use appropriate validation mode
                validation_mode = validator.suggest_mode(
                    "events.register_events", params
                )
                validated_params = validator.validate_tool_params(
                    "events.register_events", params, validation_mode
                )

                # Execute with appropriate identity
                result = await identity_manager.execute_with_identity(
                    "events.register_events",
                    validated_params,
                    _execute_register_events,
                )

                track_tool_call("register_events")
                return result

            except Exception as e:
                track_tool_error("register_events", str(e))
                logger.error(f"Error in register_events: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "event_types": event_types,
                }


async def _execute_register_events(client: Any, params: dict[str, Any]) -> EventQueue:
    """Execute event registration with Zulip client."""
    try:
        # Prepare registration parameters
        register_params = {
            "event_types": params["event_types"],
            "all_public_streams": params.get("all_public_streams", False),
            "slim_presence": params.get("slim_presence", False),
            "include_subscribers": params.get("include_subscribers", False),
            "client_gravatar": params.get("client_gravatar", False),
        }

        # Add narrow filters if provided (only for message events)
        if params.get("narrow") and "message" in params["event_types"]:
            register_params["narrow"] = _convert_narrow_to_api_format(params["narrow"])

        # Add fetch event types for initial state
        if params.get("fetch_event_types"):
            register_params["fetch_event_types"] = params["fetch_event_types"]

        # Add client capabilities
        if params.get("client_capabilities"):
            register_params["client_capabilities"] = params["client_capabilities"]

        # Register for events
        result = client.register(**register_params)

        if result.get("result") == "success":
            queue_id = result.get("queue_id")
            last_event_id = result.get("last_event_id", -1)

            # Track the queue for cleanup
            _active_queues[queue_id] = {
                "created_at": asyncio.get_event_loop().time(),
                "lifespan": params.get("queue_lifespan_secs", 300),
                "client": client,
                "event_types": params["event_types"],
            }

            # Schedule cleanup
            asyncio.create_task(_schedule_queue_cleanup(queue_id))

            return {
                "status": "success",
                "queue_id": queue_id,
                "last_event_id": last_event_id,
                "event_types": params["event_types"],
                "lifespan_seconds": params.get("queue_lifespan_secs", 300),
                "max_message_id": result.get("max_message_id"),
                "realm_user": result.get("realm_user", {}),
                "initial_state": {
                    key: value
                    for key, value in result.items()
                    if key not in ["result", "msg", "queue_id", "last_event_id"]
                },
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to register for events"),
                "event_types": params["event_types"],
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "event_types": params["event_types"],
        }


async def _schedule_queue_cleanup(queue_id: str) -> None:
    """Schedule automatic cleanup of event queue."""
    try:
        queue_info = _active_queues.get(queue_id)
        if not queue_info:
            return

        # Wait for the lifespan duration
        await asyncio.sleep(queue_info["lifespan"])

        # Clean up the queue
        if queue_id in _active_queues:
            try:
                client = queue_info["client"]
                client.deregister(queue_id)
                logger.info(f"Auto-cleaned up event queue: {queue_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up event queue {queue_id}: {e}")
            finally:
                _active_queues.pop(queue_id, None)

    except Exception as e:
        logger.error(f"Error in queue cleanup for {queue_id}: {e}")


async def get_events(
    queue_id: str,
    last_event_id: int,
    dont_block: bool = False,  # Long-polling support
    timeout: int = 10,
    # Expert parameters
    user_client: str | None = None,
    apply_markdown: bool = True,
    client_gravatar: bool = False,
) -> EventBatch:
    """Poll events from queue (stateless).

    Args:
        queue_id: Queue ID from register_events
        last_event_id: Last processed event ID
        dont_block: If True, return immediately even if no events
        timeout: Timeout in seconds for long-polling
        user_client: User client identifier
        apply_markdown: Apply markdown formatting to content
        client_gravatar: Include gravatar URLs

    Returns:
        Dictionary with events and queue information

    Raises:
        ValidationError: If parameters are invalid
        PermissionError: If user lacks required permissions
        ZulipMCPError: If Zulip API call fails
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_events"}):
        with LogContext(logger, tool="get_events", queue_id=queue_id):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "queue_id": queue_id,
                    "last_event_id": last_event_id,
                    "dont_block": dont_block,
                    "timeout": timeout,
                    "user_client": user_client,
                    "apply_markdown": apply_markdown,
                    "client_gravatar": client_gravatar,
                }

                # Use appropriate validation mode
                validation_mode = validator.suggest_mode("events.get_events", params)
                validated_params = validator.validate_tool_params(
                    "events.get_events", params, validation_mode
                )

                # Execute with appropriate identity
                result = await identity_manager.execute_with_identity(
                    "events.get_events",
                    validated_params,
                    _execute_get_events,
                )

                track_tool_call("get_events")
                return result

            except Exception as e:
                track_tool_error("get_events", str(e))
                logger.error(f"Error in get_events: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "queue_id": queue_id,
                }


async def _execute_get_events(client: Any, params: dict[str, Any]) -> EventBatch:
    """Execute get events with Zulip client."""
    try:
        # Prepare get events parameters
        get_params = {
            "queue_id": params["queue_id"],
            "last_event_id": params["last_event_id"],
        }

        # Add optional parameters
        if params.get("dont_block"):
            get_params["dont_block"] = True
        else:
            # Use timeout for long-polling
            get_params["timeout"] = params.get("timeout", 10)

        if params.get("user_client"):
            get_params["user_client"] = params["user_client"]
        if params.get("apply_markdown") is not None:
            get_params["apply_markdown"] = params["apply_markdown"]
        if params.get("client_gravatar") is not None:
            get_params["client_gravatar"] = params["client_gravatar"]

        # Get events from queue
        result = client.get_events(**get_params)

        if result.get("result") == "success":
            events = result.get("events", [])

            return {
                "status": "success",
                "queue_id": params["queue_id"],
                "events": events,
                "event_count": len(events),
                "found_newest": result.get("found_newest", False),
                "last_event_id": (
                    events[-1]["id"] if events else params["last_event_id"]
                ),
                "queue_still_valid": True,  # Assume valid if we got events
            }
        else:
            # Check if queue is invalid
            error_msg = result.get("msg", "")
            queue_invalid = "queue" in error_msg.lower() and (
                "invalid" in error_msg.lower() or "expired" in error_msg.lower()
            )

            return {
                "status": "error",
                "error": error_msg or "Failed to get events",
                "queue_id": params["queue_id"],
                "queue_still_valid": not queue_invalid,
            }

    except Exception as e:
        # Check if it's a queue-related error
        error_str = str(e).lower()
        queue_invalid = "queue" in error_str and (
            "invalid" in error_str or "expired" in error_str
        )

        return {
            "status": "error",
            "error": str(e),
            "queue_id": params["queue_id"],
            "queue_still_valid": not queue_invalid,
        }


async def listen_events(
    event_types: list[EventType],
    callback_url: str | None = None,  # Webhook support
    filters: dict[str, Any] | None = None,
    duration: int = 300,  # Auto-stop after duration
    # Advanced parameters
    narrow: list[NarrowFilter | dict[str, Any]] | None = None,
    all_public_streams: bool = False,
    poll_interval: int = 1,  # Polling interval in seconds
    max_events_per_poll: int = 100,
) -> dict[str, Any]:
    """Simple event listener with callback support.

    Args:
        event_types: Types of events to listen for
        callback_url: Optional webhook URL for event delivery
        filters: Optional event filters
        duration: Maximum duration to listen (seconds)
        narrow: Message filters (only applies to message events)
        all_public_streams: Subscribe to all public streams
        poll_interval: Seconds between polls
        max_events_per_poll: Maximum events to process per poll

    Yields:
        Individual events as they arrive

    Raises:
        ValidationError: If parameters are invalid
        PermissionError: If user lacks required permissions
        ZulipMCPError: If Zulip API call fails
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "listen_events"}):
        with LogContext(
            logger, tool="listen_events", event_types=event_types, duration=duration
        ):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "event_types": event_types,
                    "callback_url": callback_url,
                    "filters": filters,
                    "duration": duration,
                    "narrow": narrow,
                    "all_public_streams": all_public_streams,
                    "poll_interval": poll_interval,
                    "max_events_per_poll": max_events_per_poll,
                }

                # Use appropriate validation mode
                validation_mode = validator.suggest_mode("events.listen_events", params)
                validated_params = validator.validate_tool_params(
                    "events.listen_events", params, validation_mode
                )

                # Execute with appropriate identity
                result = await identity_manager.execute_with_identity(
                    "events.listen_events",
                    validated_params,
                    _execute_listen_events,
                )

                track_tool_call("listen_events")
                return result

            except Exception as e:
                track_tool_error("listen_events", str(e))
                logger.error(f"Error in listen_events: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "event_types": event_types,
                }


async def _execute_listen_events(client: Any, params: dict[str, Any]) -> dict[str, Any]:
    """Execute event listening with Zulip client."""
    try:
        # Register for events first
        register_result = await _execute_register_events(client, params)

        if register_result.get("status") != "success":
            return register_result

        queue_id = register_result["queue_id"]
        last_event_id = register_result["last_event_id"]
        start_time = asyncio.get_event_loop().time()
        duration = params.get("duration", 300)
        poll_interval = params.get("poll_interval", 1)
        max_events_total = params.get("max_events_per_poll", 100)

        logger.info(f"Started listening for events on queue {queue_id} for {duration}s")

        collected_events = []
        webhook_sent_count = 0

        try:
            while True:
                # Check duration limit
                if asyncio.get_event_loop().time() - start_time >= duration:
                    logger.info(f"Event listening duration ({duration}s) reached")
                    break

                # Get events
                get_params = {
                    "queue_id": queue_id,
                    "last_event_id": last_event_id,
                    "timeout": min(poll_interval, 10),  # Don't wait too long
                }

                events_result = await _execute_get_events(client, get_params)

                if events_result.get("status") == "success":
                    events = events_result.get("events", [])

                    # Process events (up to max limit)
                    for event in events[:max_events_total]:
                        # Apply filters if specified
                        if _event_matches_filters(event, params.get("filters")):
                            # Send to webhook if configured
                            if params.get("callback_url"):
                                asyncio.create_task(
                                    _send_webhook(params["callback_url"], event)
                                )
                                webhook_sent_count += 1

                            collected_events.append(event)

                        last_event_id = event["id"]

                    # If we hit the max events limit, continue immediately
                    if len(events) >= max_events_total:
                        continue

                elif not events_result.get("queue_still_valid", True):
                    # Queue is invalid, need to re-register
                    logger.warning(f"Queue {queue_id} became invalid, re-registering")
                    register_result = await _execute_register_events(client, params)

                    if register_result.get("status") != "success":
                        break

                    queue_id = register_result["queue_id"]
                    last_event_id = register_result["last_event_id"]
                    continue
                else:
                    # Other error, log it and continue
                    logger.warning(f"Event polling error: {events_result}")

                # Wait before next poll (if we didn't get many events)
                if len(events) < max_events_total:
                    await asyncio.sleep(poll_interval)

        finally:
            # Clean up the queue
            try:
                if queue_id in _active_queues:
                    client.deregister(queue_id)
                    _active_queues.pop(queue_id, None)
                    logger.info(f"Cleaned up event queue: {queue_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up event queue {queue_id}: {e}")

        # Return collected results
        return {
            "status": "success",
            "events": collected_events,
            "total_events": len(collected_events),
            "webhook_notifications_sent": webhook_sent_count,
            "duration_seconds": int(asyncio.get_event_loop().time() - start_time),
            "queue_id": queue_id,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "event_types": params["event_types"],
        }


def _event_matches_filters(
    event: dict[str, Any], filters: dict[str, Any] | None
) -> bool:
    """Check if an event matches the specified filters."""
    if not filters:
        return True

    for key, expected_value in filters.items():
        if key not in event:
            return False

        event_value = event[key]

        # Handle different filter types
        if isinstance(expected_value, list):
            if event_value not in expected_value:
                return False
        elif isinstance(expected_value, dict):
            # Nested object matching
            if not isinstance(event_value, dict):
                return False
            for nested_key, nested_value in expected_value.items():
                if event_value.get(nested_key) != nested_value:
                    return False
        else:
            # Direct value matching
            if event_value != expected_value:
                return False

    return True


async def _send_webhook(callback_url: str, event: dict[str, Any]) -> None:
    """Send event to webhook URL."""
    try:
        import aiohttp  # type: ignore[import-not-found]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                callback_url,
                json=event,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status >= 400:
                    logger.warning(
                        f"Webhook returned status {response.status} for URL: {callback_url}"
                    )
                else:
                    logger.debug(f"Successfully sent event to webhook: {callback_url}")

    except Exception as e:
        logger.error(f"Failed to send webhook to {callback_url}: {e}")


def cleanup_expired_queues() -> None:
    """Clean up expired event queues."""
    current_time = asyncio.get_event_loop().time()
    expired_queues = []

    for queue_id, queue_info in _active_queues.items():
        if current_time - queue_info["created_at"] > queue_info["lifespan"]:
            expired_queues.append(queue_id)

    for queue_id in expired_queues:
        asyncio.create_task(_schedule_queue_cleanup(queue_id))


def get_active_queues() -> dict[str, dict[str, Any]]:
    """Get information about active event queues."""
    current_time = asyncio.get_event_loop().time()
    result = {}

    for queue_id, queue_info in _active_queues.items():
        result[queue_id] = {
            "event_types": queue_info["event_types"],
            "created_at": queue_info["created_at"],
            "lifespan": queue_info["lifespan"],
            "age_seconds": current_time - queue_info["created_at"],
            "expires_in_seconds": queue_info["lifespan"]
            - (current_time - queue_info["created_at"]),
        }

    return result


def register_events_v25_tools(mcp: Any) -> None:
    """Register all events v2.5 tools with the MCP server.

    Args:
        mcp: FastMCP instance to register tools on
    """
    mcp.tool(description="Register for real-time events without persistence")(
        register_events
    )
    mcp.tool(description="Poll events from queue (stateless)")(get_events)
    mcp.tool(description="Simple event listener with callback support")(listen_events)
