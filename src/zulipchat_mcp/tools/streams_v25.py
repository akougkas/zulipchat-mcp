"""Consolidated stream management tools for ZulipChat MCP v2.5.0.

This module implements the 3 consolidated stream management tools according to PLAN-REFACTOR.md:
1. manage_streams() - List, create, update, delete, subscribe operations
2. manage_topics() - List, move, delete, mark_read, mute, unmute operations
3. get_stream_info() - Comprehensive stream information retrieval

Features:
- IdentityManager integration for user/bot/admin switching
- ParameterValidator for progressive disclosure
- ErrorHandler for comprehensive retry logic
- Bulk stream operations and enhanced topic management
- Comprehensive stream information with optional details
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.error_handling import get_error_handler
from ..core.identity import IdentityManager
from ..core.validation import ParameterValidator
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error

logger = get_logger(__name__)

# Response type definitions
StreamResponse = dict[str, Any]
TopicResponse = dict[str, Any]
StreamInfoResponse = dict[str, Any]

# Global instances
_config_manager: ConfigManager | None = None
_identity_manager: IdentityManager | None = None
_parameter_validator: ParameterValidator | None = None
_error_handler = get_error_handler()


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


async def manage_streams(
    operation: Literal[
        "list", "create", "update", "delete", "subscribe", "unsubscribe"
    ],
    stream_ids: list[int] | None = None,  # Bulk operations
    stream_names: list[str] | None = None,
    properties: dict[str, Any] | None = None,  # Stream properties for create/update
    # Subscription options
    principals: list[str] | None = None,  # Users to also subscribe
    announce: bool = False,
    invite_only: bool = False,
    # Advanced filters for list
    include_public: bool = True,
    include_subscribed: bool = True,
    include_all_active: bool = False,
    # Expert parameters
    authorization_errors_fatal: bool = True,
    history_public_to_subscribers: bool | None = None,
    stream_post_policy: int | None = None,
    message_retention_days: int | None = None,
) -> StreamResponse:
    """Manage streams with bulk operations support.

    Replaces: get_streams, create_stream, rename_stream, archive_stream

    Args:
        operation: Operation to perform (list/create/update/delete/subscribe/unsubscribe)
        stream_ids: List of stream IDs for bulk operations
        stream_names: List of stream names for operations
        properties: Stream properties for create/update operations
        principals: Users to subscribe/unsubscribe (in addition to current user)
        announce: Whether to announce new stream creation
        invite_only: Whether stream is invite-only (for create)
        include_public: Include public streams in list operation
        include_subscribed: Include subscribed streams in list operation
        include_all_active: Include all active streams (admin only)
        authorization_errors_fatal: Whether auth errors should be fatal
        history_public_to_subscribers: Whether message history is public
        stream_post_policy: Who can post to stream (create/update)
        message_retention_days: Message retention policy (admin only)

    Returns:
        Dictionary with operation results and stream information

    Raises:
        ValidationError: If parameters are invalid
        PermissionError: If user lacks required permissions
        ZulipMCPError: If Zulip API call fails
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "manage_streams"}):
        with LogContext(logger, tool="manage_streams", operation=operation):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "operation": operation,
                    "stream_ids": stream_ids,
                    "stream_names": stream_names,
                    "properties": properties,
                    "principals": principals,
                    "announce": announce,
                    "invite_only": invite_only,
                    "include_public": include_public,
                    "include_subscribed": include_subscribed,
                    "include_all_active": include_all_active,
                    "authorization_errors_fatal": authorization_errors_fatal,
                    "history_public_to_subscribers": history_public_to_subscribers,
                    "stream_post_policy": stream_post_policy,
                    "message_retention_days": message_retention_days,
                }

                # Use appropriate validation mode based on parameters
                validation_mode = validator.suggest_mode(
                    "streams.manage_streams", params
                )
                validated_params = validator.validate_tool_params(
                    "streams.manage_streams", params, validation_mode
                )

                # Execute with appropriate identity
                result = await identity_manager.execute_with_identity(
                    "streams.manage_streams",
                    validated_params,
                    _execute_stream_operation,
                )

                track_tool_call("manage_streams")
                return result

            except Exception as e:
                track_tool_error("manage_streams", str(e))
                logger.error(f"Error in manage_streams: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "operation": operation,
                }


async def _execute_stream_operation(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> StreamResponse:
    """Execute stream operation with Zulip client."""
    operation = params["operation"]

    try:
        if operation == "list":
            return await _list_streams(client, params)
        elif operation == "create":
            return await _create_streams(client, params)
        elif operation == "update":
            return await _update_streams(client, params)
        elif operation == "delete":
            return await _delete_streams(client, params)
        elif operation == "subscribe":
            return await _subscribe_streams(client, params)
        elif operation == "unsubscribe":
            return await _unsubscribe_streams(client, params)
        else:
            return {
                "status": "error",
                "error": f"Unknown operation: {operation}",
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "operation": operation,
        }


def _resolve_stream_id(client: ZulipClientWrapper, ident: int | str) -> int | None:
    """Resolve a stream identifier which may be an id (int) or name (str)."""
    if isinstance(ident, int):
        return ident
    try:
        res = client.get_stream_id(ident)
        if res.get("result") == "success":
            # Zulip returns either {"stream_id": id} or {"stream": {"stream_id": id}}
            if "stream_id" in res:
                return int(res["stream_id"])  # type: ignore[arg-type]
            stream_obj = res.get("stream", {})
            return int(stream_obj.get("stream_id")) if stream_obj else None
    except Exception:
        return None
    return None


async def _list_streams(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> StreamResponse:
    """List streams based on filters."""
    request_params = {}

    if params.get("include_public"):
        request_params["include_public"] = True
    if params.get("include_subscribed"):
        request_params["include_subscribed"] = True
    if params.get("include_all_active"):
        request_params["include_all_active"] = True

    # Use ZulipClientWrapper get_streams with automatic caching
    result = client.get_streams(
        include_subscribed=bool(request_params.get("include_subscribed", True)),
        force_fresh=False,
    )

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "list",
            "streams": result.get("streams", []),
            "count": len(result.get("streams", [])),
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to list streams"),
            "operation": "list",
        }


async def _create_streams(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> StreamResponse:
    """Create new streams."""
    if not params.get("stream_names"):
        return {
            "status": "error",
            "error": "stream_names required for create operation",
            "operation": "create",
        }

    subscriptions = []
    for name in params["stream_names"]:
        stream_spec = {"name": name}
        if params.get("properties"):
            stream_spec.update(params["properties"])
        if params.get("invite_only") is not None:
            stream_spec["invite_only"] = params["invite_only"]
        subscriptions.append(stream_spec)

    request_params = {
        "subscriptions": subscriptions,
        "announce": params.get("announce", False),
        "authorization_errors_fatal": params.get("authorization_errors_fatal", True),
    }

    if params.get("principals"):
        request_params["principals"] = params["principals"]
    if params.get("history_public_to_subscribers") is not None:
        request_params["history_public_to_subscribers"] = params[
            "history_public_to_subscribers"
        ]
    if params.get("stream_post_policy") is not None:
        request_params["stream_post_policy"] = params["stream_post_policy"]
    if params.get("message_retention_days") is not None:
        request_params["message_retention_days"] = params["message_retention_days"]

    result = client.add_subscriptions(**request_params)

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "create",
            "subscribed": result.get("subscribed", {}),
            "already_subscribed": result.get("already_subscribed", {}),
            "unauthorized": result.get("unauthorized", []),
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to create streams"),
            "operation": "create",
        }


async def _update_streams(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> StreamResponse:
    """Update existing streams."""
    if not (params.get("stream_ids") or params.get("stream_names")):
        return {
            "status": "error",
            "error": "stream_ids or stream_names required for update operation",
            "operation": "update",
        }

    if not params.get("properties"):
        return {
            "status": "error",
            "error": "properties required for update operation",
            "operation": "update",
        }

    results = []
    stream_identifiers = params.get("stream_ids") or params.get("stream_names") or []

    # Normalize to numeric stream ids
    normalized_ids: list[int] = []
    for ident in stream_identifiers:
        sid = _resolve_stream_id(client, ident)
        if sid is not None:
            normalized_ids.append(sid)

    for stream_id in normalized_ids:
        for property_name, value in params["properties"].items():
            try:
                result = client.update_stream(
                    stream_id=stream_id, **{property_name: value}
                )
                results.append(
                    {
                        "stream_id": stream_id,
                        "property": property_name,
                        "status": (
                            "success" if result.get("result") == "success" else "error"
                        ),
                        "message": result.get("msg", ""),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "stream_id": stream_id,
                        "property": property_name,
                        "status": "error",
                        "message": str(e),
                    }
                )

    return {
        "status": "success",
        "operation": "update",
        "results": results,
    }


async def _delete_streams(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> StreamResponse:
    """Delete streams."""
    if not (params.get("stream_ids") or params.get("stream_names")):
        return {
            "status": "error",
            "error": "stream_ids or stream_names required for delete operation",
            "operation": "delete",
        }

    results = []
    stream_identifiers = params.get("stream_ids") or params.get("stream_names") or []

    normalized_ids: list[int] = []
    for ident in stream_identifiers:
        sid = _resolve_stream_id(client, ident)
        if sid is not None:
            normalized_ids.append(sid)

    for stream_id in normalized_ids:
        try:
            result = client.delete_stream(stream_id)
            results.append(
                {
                    "stream_id": stream_id,
                    "status": (
                        "success" if result.get("result") == "success" else "error"
                    ),
                    "message": result.get("msg", ""),
                }
            )
        except Exception as e:
            results.append(
                {
                    "stream_id": stream_id,
                    "status": "error",
                    "message": str(e),
                }
            )

    return {
        "status": "success",
        "operation": "delete",
        "results": results,
    }


async def _subscribe_streams(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> StreamResponse:
    """Subscribe to streams."""
    if not (params.get("stream_ids") or params.get("stream_names")):
        return {
            "status": "error",
            "error": "stream_ids or stream_names required for subscribe operation",
            "operation": "subscribe",
        }

    # Convert to subscription format
    subscriptions = []
    if params.get("stream_names"):
        subscriptions = [{"name": name} for name in params["stream_names"]]
    elif params.get("stream_ids"):
        # Need to get stream names from IDs
        for stream_id in params["stream_ids"]:
            stream_info = client.get_stream_id(stream_id)
            if stream_info.get("result") == "success":
                subscriptions.append(
                    {"name": stream_info.get("stream", {}).get("name", str(stream_id))}
                )

    request_params = {
        "subscriptions": subscriptions,
        "authorization_errors_fatal": params.get("authorization_errors_fatal", True),
    }

    if params.get("principals"):
        request_params["principals"] = params["principals"]

    result = client.add_subscriptions(**request_params)

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "subscribe",
            "subscribed": result.get("subscribed", {}),
            "already_subscribed": result.get("already_subscribed", {}),
            "unauthorized": result.get("unauthorized", []),
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to subscribe to streams"),
            "operation": "subscribe",
        }


async def _unsubscribe_streams(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> StreamResponse:
    """Unsubscribe from streams."""
    if not (params.get("stream_ids") or params.get("stream_names")):
        return {
            "status": "error",
            "error": "stream_ids or stream_names required for unsubscribe operation",
            "operation": "unsubscribe",
        }

    stream_names = params.get("stream_names", [])
    if params.get("stream_ids") and not stream_names:
        # Convert IDs to names
        for stream_id in params["stream_ids"]:
            stream_info = client.get_stream_id(stream_id)
            if stream_info.get("result") == "success":
                stream_names.append(
                    stream_info.get("stream", {}).get("name", str(stream_id))
                )

    request_params = {"subscriptions": stream_names}
    if params.get("principals"):
        request_params["principals"] = params["principals"]

    result = client.remove_subscriptions(**request_params)

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "unsubscribe",
            "removed": result.get("removed", []),
            "not_removed": result.get("not_removed", []),
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to unsubscribe from streams"),
            "operation": "unsubscribe",
        }


async def manage_topics(
    stream_id: int,
    operation: Literal["list", "move", "delete", "mark_read", "mute", "unmute"],
    source_topic: str | None = None,
    target_topic: str | None = None,
    target_stream_id: int | None = None,
    # NEW: Topic propagation control
    propagate_mode: str = "change_all",
    include_muted: bool = True,
    max_results: int = 100,
    # Expert parameters for topic operations
    send_notification_to_old_thread: bool = True,
    send_notification_to_new_thread: bool = True,
) -> TopicResponse:
    """Bulk topic operations within streams.

    Args:
        stream_id: Stream ID containing the topic
        operation: Operation to perform on topics
        source_topic: Source topic name (for move/delete operations)
        target_topic: Target topic name (for move operations)
        target_stream_id: Target stream ID (for cross-stream moves)
        propagate_mode: How to propagate changes (change_all/change_one/change_later)
        include_muted: Include muted topics in list operation
        max_results: Maximum number of topics to return
        send_notification_to_old_thread: Send notification to old thread (move)
        send_notification_to_new_thread: Send notification to new thread (move)

    Returns:
        Dictionary with operation results and topic information

    Raises:
        ValidationError: If parameters are invalid
        PermissionError: If user lacks required permissions
        ZulipMCPError: If Zulip API call fails
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "manage_topics"}):
        with LogContext(
            logger, tool="manage_topics", operation=operation, stream_id=stream_id
        ):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "stream_id": stream_id,
                    "operation": operation,
                    "source_topic": source_topic,
                    "target_topic": target_topic,
                    "target_stream_id": target_stream_id,
                    "propagate_mode": propagate_mode,
                    "include_muted": include_muted,
                    "max_results": max_results,
                    "send_notification_to_old_thread": send_notification_to_old_thread,
                    "send_notification_to_new_thread": send_notification_to_new_thread,
                }

                # Use appropriate validation mode
                validation_mode = validator.suggest_mode(
                    "streams.manage_topics", params
                )
                validated_params = validator.validate_tool_params(
                    "streams.manage_topics", params, validation_mode
                )

                # Execute with appropriate identity
                result = await identity_manager.execute_with_identity(
                    "streams.manage_topics",
                    validated_params,
                    _execute_topic_operation,
                )

                track_tool_call("manage_topics")
                return result

            except Exception as e:
                track_tool_error("manage_topics", str(e))
                logger.error(f"Error in manage_topics: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "operation": operation,
                    "stream_id": stream_id,
                }


async def _execute_topic_operation(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> TopicResponse:
    """Execute topic operation with Zulip client."""
    operation = params["operation"]

    try:
        if operation == "list":
            return await _list_topics(client, params)
        elif operation == "move":
            return await _move_topic(client, params)
        elif operation == "delete":
            return await _delete_topic(client, params)
        elif operation == "mark_read":
            return await _mark_topic_read(client, params)
        elif operation == "mute":
            return await _mute_topic(client, params)
        elif operation == "unmute":
            return await _unmute_topic(client, params)
        else:
            return {
                "status": "error",
                "error": f"Unknown operation: {operation}",
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "operation": operation,
        }


async def _list_topics(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> TopicResponse:
    """List topics in a stream."""
    result = client.get_stream_topics(stream_id=params["stream_id"])

    if result.get("result") == "success":
        topics = result.get("topics", [])

        # Apply max_results limit
        max_results = params.get("max_results", 100)
        if len(topics) > max_results:
            topics = topics[:max_results]

        return {
            "status": "success",
            "operation": "list",
            "stream_id": params["stream_id"],
            "topics": topics,
            "count": len(topics),
            "truncated": len(result.get("topics", [])) > max_results,
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to list topics"),
            "operation": "list",
            "stream_id": params["stream_id"],
        }


async def _move_topic(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> TopicResponse:
    """Move topic to different name or stream."""
    if not params.get("source_topic"):
        return {
            "status": "error",
            "error": "source_topic required for move operation",
            "operation": "move",
        }

    # Prepare move parameters
    move_params = {
        "stream_id": params["stream_id"],
        "topic": params["source_topic"],
        "propagate_mode": params.get("propagate_mode", "change_all"),
        "send_notification_to_old_thread": params.get(
            "send_notification_to_old_thread", True
        ),
        "send_notification_to_new_thread": params.get(
            "send_notification_to_new_thread", True
        ),
    }

    # Determine move type
    if params.get("target_topic"):
        move_params["topic"] = params["target_topic"]

    if params.get("target_stream_id"):
        move_params["stream_id"] = params["target_stream_id"]

    # Use update_message API for topic moves
    # Find a message in the topic to move
    narrow = [
        {"operator": "stream", "operand": str(params["stream_id"])},
        {"operator": "topic", "operand": params["source_topic"]},
    ]

    try:
        messages_result = client.get_messages_raw(
            anchor="newest", num_before=1, num_after=0, narrow=narrow
        )
    except Exception:
        messages_result = client.get_messages(
            {"anchor": "newest", "num_before": 1, "num_after": 0, "narrow": narrow}
        )

    if messages_result.get("result") != "success" or not messages_result.get(
        "messages"
    ):
        return {
            "status": "error",
            "error": "No messages found in topic to move",
            "operation": "move",
            "stream_id": params["stream_id"],
            "source_topic": params["source_topic"],
        }

    message_id = messages_result["messages"][0]["id"]

    # Perform the move
    result = client.update_message({"message_id": message_id, **move_params})

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "move",
            "stream_id": params["stream_id"],
            "source_topic": params["source_topic"],
            "target_topic": params.get("target_topic"),
            "target_stream_id": params.get("target_stream_id"),
            "propagate_mode": params.get("propagate_mode"),
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to move topic"),
            "operation": "move",
            "stream_id": params["stream_id"],
            "source_topic": params["source_topic"],
        }


async def _delete_topic(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> TopicResponse:
    """Delete a topic (admin only)."""
    if not params.get("source_topic"):
        return {
            "status": "error",
            "error": "source_topic required for delete operation",
            "operation": "delete",
        }

    result = client.delete_topic(
        stream_id=params["stream_id"], topic_name=params["source_topic"]
    )

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "delete",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to delete topic"),
            "operation": "delete",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }


async def _mark_topic_read(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> TopicResponse:
    """Mark all messages in topic as read."""
    if not params.get("source_topic"):
        return {
            "status": "error",
            "error": "source_topic required for mark_read operation",
            "operation": "mark_read",
        }

    result = client.mark_topic_as_read(
        stream_id=params["stream_id"], topic_name=params["source_topic"]
    )

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "mark_read",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to mark topic as read"),
            "operation": "mark_read",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }


async def _mute_topic(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> TopicResponse:
    """Mute a topic."""
    if not params.get("source_topic"):
        return {
            "status": "error",
            "error": "source_topic required for mute operation",
            "operation": "mute",
        }

    try:
        result = client.mute_topic(
            stream_id=params["stream_id"], topic=params["source_topic"]
        )
    except TypeError:
        result = client.mute_topic(
            stream_id=params["stream_id"], topic_name=params["source_topic"]
        )

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "mute",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to mute topic"),
            "operation": "mute",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }


async def _unmute_topic(
    client: ZulipClientWrapper, params: dict[str, Any]
) -> TopicResponse:
    """Unmute a topic."""
    if not params.get("source_topic"):
        return {
            "status": "error",
            "error": "source_topic required for unmute operation",
            "operation": "unmute",
        }

    try:
        result = client.unmute_topic(
            stream_id=params["stream_id"], topic=params["source_topic"]
        )
    except TypeError:
        result = client.unmute_topic(
            stream_id=params["stream_id"], topic_name=params["source_topic"]
        )

    if result.get("result") == "success":
        return {
            "status": "success",
            "operation": "unmute",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }
    else:
        return {
            "status": "error",
            "error": result.get("msg", "Failed to unmute topic"),
            "operation": "unmute",
            "stream_id": params["stream_id"],
            "topic": params["source_topic"],
        }


async def get_stream_info(
    stream_id: int | None = None,
    stream_name: str | None = None,
    include_topics: bool = False,
    include_subscribers: bool = False,
    include_settings: bool = False,
    # Expert parameters
    include_web_public: bool = False,
    include_default: bool = False,
) -> StreamInfoResponse:
    """Get comprehensive stream information.

    Args:
        stream_id: Stream ID to get info for
        stream_name: Stream name to get info for
        include_topics: Include list of topics in stream
        include_subscribers: Include list of subscribers
        include_settings: Include stream settings and permissions
        include_web_public: Include web-public stream info
        include_default: Include default stream info

    Returns:
        Dictionary with comprehensive stream information

    Raises:
        ValidationError: If parameters are invalid
        PermissionError: If user lacks required permissions
        ZulipMCPError: If Zulip API call fails
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_stream_info"}):
        with LogContext(
            logger, tool="get_stream_info", stream_id=stream_id, stream_name=stream_name
        ):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "stream_id": stream_id,
                    "stream_name": stream_name,
                    "include_topics": include_topics,
                    "include_subscribers": include_subscribers,
                    "include_settings": include_settings,
                    "include_web_public": include_web_public,
                    "include_default": include_default,
                }

                # Use appropriate validation mode
                validation_mode = validator.suggest_mode(
                    "streams.get_stream_info", params
                )
                validated_params = validator.validate_tool_params(
                    "streams.get_stream_info", params, validation_mode
                )

                # Execute with appropriate identity
                result = await identity_manager.execute_with_identity(
                    "streams.get_stream_info",
                    validated_params,
                    _execute_get_stream_info,
                )

                track_tool_call("get_stream_info")
                return result

            except Exception as e:
                track_tool_error("get_stream_info", str(e))
                logger.error(f"Error in get_stream_info: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "stream_id": stream_id,
                    "stream_name": stream_name,
                }


async def _execute_get_stream_info(
    client, params: dict[str, Any]
) -> StreamInfoResponse:
    """Get comprehensive stream information."""
    try:
        stream_info = {}

        # Get basic stream info
        if params.get("stream_id"):
            result = client.get_stream_id(params["stream_id"])
            if result.get("result") == "success":
                stream_info.update(result.get("stream", {}))
                stream_id = params["stream_id"]
            else:
                return {
                    "status": "error",
                    "error": result.get("msg", "Stream not found"),
                }
        elif params.get("stream_name"):
            # Use ZulipClientWrapper get_streams with automatic caching
            result = client.get_streams(include_subscribed=True, force_fresh=False)
            if result.get("result") == "success":
                for stream in result.get("streams", []):
                    if stream.get("name") == params["stream_name"]:
                        stream_info.update(stream)
                        stream_id = stream.get("stream_id")
                        break
                else:
                    return {
                        "status": "error",
                        "error": f"Stream '{params['stream_name']}' not found",
                    }
            else:
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to search for stream"),
                }
        else:
            return {
                "status": "error",
                "error": "Either stream_id or stream_name is required",
            }

        response = {
            "status": "success",
            "stream": stream_info,
        }

        # Include topics if requested
        if params.get("include_topics"):
            topics_result = client.get_stream_topics(stream_id=stream_id)
            if topics_result.get("result") == "success":
                response["topics"] = topics_result.get("topics", [])
            else:
                response["topics_error"] = topics_result.get(
                    "msg", "Failed to get topics"
                )

        # Include subscribers if requested
        if params.get("include_subscribers"):
            subs_result = client.get_subscribers(stream_id=stream_id)
            if subs_result.get("result") == "success":
                response["subscribers"] = subs_result.get("subscribers", [])
            else:
                response["subscribers_error"] = subs_result.get(
                    "msg", "Failed to get subscribers"
                )

        # Include settings if requested
        if params.get("include_settings"):
            # Get user's subscription settings for this stream
            my_subs_result = client.get_subscriptions()
            if my_subs_result.get("result") == "success":
                for sub in my_subs_result.get("subscriptions", []):
                    if sub.get("stream_id") == stream_id:
                        response["subscription_settings"] = sub
                        break

        return response

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def stream_analytics(
    stream_id: int | None = None,
    stream_name: str | None = None,
    time_period: Literal["day", "week", "month", "year"] = "week",
    include_message_stats: bool = True,
    include_user_activity: bool = True,
    include_topic_stats: bool = True,
) -> dict[str, Any]:
    """Get comprehensive stream statistics and analytics.

    This tool provides detailed analytics for streams including message counts,
    user activity, topic statistics, and growth trends.

    Args:
        stream_id: Stream ID to analyze
        stream_name: Stream name to analyze (alternative to stream_id)
        time_period: Time period for analytics
        include_message_stats: Include message count statistics
        include_user_activity: Include user activity metrics
        include_topic_stats: Include topic statistics

    Returns:
        Dictionary with comprehensive stream analytics

    Examples:
        # Get weekly analytics for a stream
        await stream_analytics(stream_id=123, time_period="week")

        # Get detailed analytics by stream name
        await stream_analytics(stream_name="general", include_user_activity=True)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "streams.analytics"}):
        with LogContext(
            logger,
            tool="stream_analytics",
            stream_id=stream_id,
            stream_name=stream_name,
        ):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                if not stream_id and not stream_name:
                    return {
                        "status": "error",
                        "error": "Either stream_id or stream_name is required",
                    }

                # Execute analytics with appropriate identity
                async def _execute_analytics(
                    client: ZulipClientWrapper, params: dict[str, Any]
                ) -> dict[str, Any]:
                    # Resolve stream_id if only name provided
                    target_stream_id = stream_id
                    if not target_stream_id and stream_name:
                        streams_result = client.get_streams(
                            include_subscribed=True, include_public=True
                        )
                        if streams_result.get("result") == "success":
                            for stream in streams_result.get("streams", []):
                                if stream.get("name") == stream_name:
                                    target_stream_id = stream.get("stream_id")
                                    break

                        if not target_stream_id:
                            return {
                                "status": "error",
                                "error": f"Stream '{stream_name}' not found",
                            }

                    analytics_data = {
                        "status": "success",
                        "stream_id": target_stream_id,
                        "stream_name": stream_name,
                        "time_period": time_period,
                        "timestamp": datetime.now().isoformat(),
                    }

                    # Get basic stream info
                    stream_result = client.get_stream_id(target_stream_id)
                    logger.debug(
                        "stream_analytics.get_stream_id",
                        extra={
                            "stream_id": target_stream_id,
                            "raw_keys": list(stream_result.keys()),
                        },
                    )
                    if stream_result.get("result") == "success":
                        try:
                            # Handle different response formats from get_stream_id
                            if "stream" in stream_result:
                                analytics_data["stream_info"] = stream_result["stream"]
                            else:
                                # Remove internal fields and use the result directly
                                stream_info = {
                                    k: v
                                    for k, v in stream_result.items()
                                    if k not in ["result", "msg"]
                                }
                                analytics_data["stream_info"] = stream_info
                        except KeyError as e:
                            # Defensive guard for unexpected shapes
                            logger.warning(
                                "Missing expected key in stream_result",
                                extra={
                                    "missing_key": str(e),
                                    "available_keys": list(stream_result.keys()),
                                },
                            )
                            analytics_data["stream_info"] = {
                                "error": "Unexpected stream info format",
                                "available_keys": list(stream_result.keys()),
                            }

                        # If stream_name was not provided, try to populate from info
                        if not analytics_data.get("stream_name"):
                            name_guess = (
                                analytics_data.get("stream_info", {}).get("name")
                                if isinstance(analytics_data.get("stream_info"), dict)
                                else None
                            )
                            if name_guess:
                                analytics_data["stream_name"] = name_guess

                    # Message statistics (approximated via message search)
                    if include_message_stats:
                        try:
                            # Search for recent messages in the stream
                            # Prefer the resolved stream name; Zulip narrow expects names
                            target_name = (
                                analytics_data.get("stream_name") or stream_name or ""
                            )
                            narrow = [{"operator": "stream", "operand": target_name}]
                            messages_request = {
                                "anchor": "newest",
                                "num_before": 1000,  # Sample size
                                "num_after": 0,
                                "narrow": narrow,
                            }
                            try:
                                messages_result = client.get_messages_raw(
                                    **messages_request
                                )
                            except Exception:
                                messages_result = client.get_messages(messages_request)

                            if messages_result.get("result") == "success":
                                messages = messages_result.get("messages", [])

                                # Calculate basic statistics
                                analytics_data["message_stats"] = {
                                    "recent_message_count": len(messages),
                                    "sample_size": min(1000, len(messages)),
                                    "note": "Statistics based on recent message sample",
                                }

                                # Calculate average message length if messages available
                                if messages:
                                    avg_length = sum(
                                        len(msg.get("content", "")) for msg in messages
                                    ) / len(messages)
                                    analytics_data["message_stats"][
                                        "average_message_length"
                                    ] = round(avg_length, 2)
                            else:
                                analytics_data["message_stats"] = {
                                    "error": "Could not retrieve message statistics"
                                }
                        except Exception as e:
                            analytics_data["message_stats"] = {
                                "error": f"Failed to calculate message stats: {str(e)}"
                            }

                    # User activity metrics
                    if include_user_activity:
                        try:
                            # Get subscribers
                            subs_result = client.get_subscribers(
                                stream_id=target_stream_id
                            )
                            logger.debug(
                                "stream_analytics.get_subscribers",
                                extra={
                                    "stream_id": target_stream_id,
                                    "shape": type(subs_result).__name__,
                                    "keys": list(subs_result.keys()),
                                    "sample": str(subs_result)[:160],
                                },
                            )
                            if subs_result.get("result") == "success":
                                subscribers = subs_result.get("subscribers", [])
                                if not isinstance(subscribers, list):
                                    subscribers = []
                                analytics_data["user_activity"] = {
                                    "total_subscribers": len(subscribers),
                                    "subscriber_list": subscribers[
                                        :20
                                    ],  # First 20 subscribers
                                }
                            else:
                                analytics_data["user_activity"] = {
                                    "error": "Could not retrieve subscriber information"
                                }
                        except Exception as e:
                            import traceback

                            analytics_data["user_activity"] = {
                                "error": f"Failed to get user activity: {str(e)}",
                                "error_type": type(e).__name__,
                                "traceback": traceback.format_exc()[
                                    -500:
                                ],  # Last 500 chars
                            }

                    # Topic statistics
                    if include_topic_stats:
                        try:
                            topics_result = client.get_stream_topics(
                                stream_id=target_stream_id
                            )
                            logger.debug(
                                "stream_analytics.get_stream_topics",
                                extra={
                                    "stream_id": target_stream_id,
                                    "keys": list(topics_result.keys()),
                                    "count": (
                                        len(topics_result.get("topics", []))
                                        if isinstance(topics_result, dict)
                                        else None
                                    ),
                                },
                            )
                            if topics_result.get("result") == "success":
                                topics = topics_result.get("topics", [])
                                analytics_data["topic_stats"] = {
                                    "total_topics": len(topics),
                                    "recent_topics": topics[
                                        :10
                                    ],  # Most recent 10 topics
                                    "most_active_topics": sorted(
                                        topics,
                                        key=lambda t: t.get("max_id", 0)
                                        - t.get("min_id", 0),
                                        reverse=True,
                                    )[
                                        :5
                                    ],  # Top 5 by activity approximation
                                }
                            else:
                                analytics_data["topic_stats"] = {
                                    "error": "Could not retrieve topic statistics"
                                }
                        except Exception as e:
                            analytics_data["topic_stats"] = {
                                "error": f"Failed to get topic stats: {str(e)}"
                            }

                    return analytics_data

                # Pass original identifiers; inner function resolves stream_id as needed
                result = await identity_manager.execute_with_identity(
                    "streams.analytics",
                    {"stream_id": stream_id, "stream_name": stream_name},
                    _execute_analytics,
                )

                track_tool_call("streams.analytics")
                return result

            except Exception as e:
                track_tool_error("streams.analytics", str(e))
                logger.error(f"Error in stream_analytics: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "stream_id": stream_id,
                    "stream_name": stream_name,
                }


async def manage_stream_settings(
    stream_id: int,
    operation: Literal["get", "update", "notifications", "permissions"],
    # Notification settings
    notification_settings: dict[str, Any] | None = None,
    # Permission settings
    permission_updates: dict[str, Any] | None = None,
    # Stream appearance
    color: str | None = None,
    pin_to_top: bool | None = None,
) -> dict[str, Any]:
    """Manage stream notification settings and permissions.

    This tool provides comprehensive stream settings management including
    notification preferences, permissions, and appearance customization.

    Args:
        stream_id: Stream ID to manage settings for
        operation: Type of settings operation
        notification_settings: Notification preference updates
        permission_updates: Permission setting updates
        color: Stream color (hex format)
        pin_to_top: Whether to pin stream to top of sidebar

    Returns:
        Dictionary with settings operation results

    Examples:
        # Get current stream settings
        await manage_stream_settings(123, "get")

        # Update notification settings
        await manage_stream_settings(
            123, "notifications",
            notification_settings={"push_notifications": True, "email_notifications": False}
        )

        # Update stream appearance
        await manage_stream_settings(123, "update", color="#ff6600", pin_to_top=True)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "streams.settings"}):
        with LogContext(
            logger,
            tool="manage_stream_settings",
            stream_id=stream_id,
            operation=operation,
        ):
            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                if stream_id <= 0:
                    return {"status": "error", "error": "Invalid stream ID"}

                # Execute settings management
                async def _execute_settings(
                    client: ZulipClientWrapper, params: dict[str, Any]
                ) -> dict[str, Any]:
                    if operation == "get":
                        # Get current settings
                        subscription_result = client.get_subscriptions()
                        if subscription_result.get("result") == "success":
                            for sub in subscription_result.get("subscriptions", []):
                                if sub.get("stream_id") == stream_id:
                                    return {
                                        "status": "success",
                                        "operation": "get",
                                        "stream_id": stream_id,
                                        "current_settings": sub,
                                        "timestamp": datetime.now().isoformat(),
                                    }

                            return {
                                "status": "error",
                                "error": "Stream subscription not found",
                            }
                        else:
                            return {
                                "status": "error",
                                "error": f"Failed to get subscriptions: {subscription_result.get('msg')}",
                            }

                    elif operation == "update":
                        # Update stream appearance settings
                        updates = {}
                        if color is not None:
                            updates["color"] = color
                        if pin_to_top is not None:
                            updates["pin_to_top"] = pin_to_top

                        if not updates:
                            return {"status": "error", "error": "No updates specified"}

                        # Update subscription settings
                        update_result = client.update_subscription_settings(
                            [{"stream_id": stream_id, **updates}]
                        )

                        if update_result.get("result") == "success":
                            return {
                                "status": "success",
                                "operation": "update",
                                "stream_id": stream_id,
                                "updated_settings": updates,
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            return {
                                "status": "error",
                                "error": f"Failed to update settings: {update_result.get('msg')}",
                            }

                    elif operation == "notifications":
                        # Update notification settings
                        if not notification_settings:
                            return {
                                "status": "error",
                                "error": "notification_settings parameter is required",
                            }

                        # Map notification settings to Zulip format
                        zulip_settings = []
                        for setting, value in notification_settings.items():
                            zulip_settings.append(
                                {
                                    "stream_id": stream_id,
                                    "property": setting,
                                    "value": value,
                                }
                            )

                        update_result = client.update_subscription_settings(
                            zulip_settings
                        )

                        if update_result.get("result") == "success":
                            return {
                                "status": "success",
                                "operation": "notifications",
                                "stream_id": stream_id,
                                "updated_notifications": notification_settings,
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            return {
                                "status": "error",
                                "error": f"Failed to update notifications: {update_result.get('msg')}",
                            }

                    elif operation == "permissions":
                        # Update permission settings (admin operation)
                        if not permission_updates:
                            return {
                                "status": "error",
                                "error": "permission_updates parameter is required",
                            }

                        # This operation typically requires admin privileges
                        update_result = client.update_stream(
                            stream_id=stream_id, **permission_updates
                        )

                        if update_result.get("result") == "success":
                            return {
                                "status": "success",
                                "operation": "permissions",
                                "stream_id": stream_id,
                                "updated_permissions": permission_updates,
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            return {
                                "status": "error",
                                "error": f"Failed to update permissions: {update_result.get('msg')}",
                            }

                    else:
                        return {
                            "status": "error",
                            "error": f"Unknown operation: {operation}",
                        }

                result = await identity_manager.execute_with_identity(
                    "streams.settings", {"operation": operation}, _execute_settings
                )

                track_tool_call("streams.settings")
                return result

            except Exception as e:
                track_tool_error("streams.settings", str(e))
                logger.error(f"Error in manage_stream_settings: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "operation": operation,
                    "stream_id": stream_id,
                }


def register_streams_v25_tools(mcp: Any) -> None:
    """Register all streams v2.5 tools with the MCP server.

    Args:
        mcp: FastMCP instance to register tools on
    """
    mcp.tool(description="Manage streams with bulk operations support")(manage_streams)
    mcp.tool(description="Bulk topic operations within streams")(manage_topics)
    mcp.tool(description="Get comprehensive stream information")(get_stream_info)
    mcp.tool(description="Get comprehensive stream statistics and analytics")(
        stream_analytics
    )
    mcp.tool(description="Manage stream notification settings and permissions")(
        manage_stream_settings
    )
