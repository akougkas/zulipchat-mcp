"""Consolidated messaging tools for ZulipChat MCP v2.5.0.

This module implements 8 consolidated messaging tools according to PLAN-REFACTOR.md:
1. message() - Send, schedule, or draft messages
2. search_messages() - Search and retrieve messages with powerful filtering
3. edit_message() - Edit or move messages with topic management
4. bulk_operations() - Bulk message operations
5. message_history() - Get comprehensive message history and edit tracking
6. cross_post_message() - Cross-post messages between streams
7. add_reaction() - Add emoji reaction to a single message (standalone)
8. remove_reaction() - Remove emoji reaction from a single message (standalone)

Features:
- IdentityManager integration for user/bot switching
- ParameterValidator for progressive disclosure and narrow filters
- ErrorHandler for comprehensive retry logic
- Scheduled messaging support
- Advanced narrow filtering
- Bulk operations with multiple selection methods
- Simple standalone reaction management
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from ..config import ConfigManager
import builtins as _builtins
from ..core.error_handling import get_error_handler
from ..core.identity import IdentityManager, IdentityType
from ..core.security import validate_emoji
from ..core.validation import (
    NarrowFilter,
    ParameterValidator,
)
from ..services.scheduler import MessageScheduler, ScheduledMessage
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_message_sent, track_tool_call, track_tool_error
from ..utils.narrow_helpers import NarrowHelper, build_basic_narrow

logger = get_logger(__name__)

# Response type definitions
MessageResponse = dict[str, Any]
MessageList = dict[str, Any]
EditResponse = dict[str, Any]
BulkResponse = dict[str, Any]

# Global instances
_config_manager: ConfigManager | None = None
_identity_manager: IdentityManager | None = None
_parameter_validator: ParameterValidator | None = None
_error_handler = get_error_handler()

# Maximum content size (50KB) - reasonable for most LLMs
MAX_CONTENT_SIZE = 50000


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


def _truncate_content(content: str) -> str:
    """Truncate content if it exceeds maximum size."""
    if len(content) > MAX_CONTENT_SIZE:
        return content[:MAX_CONTENT_SIZE] + "\n... [Content truncated]"
    return content


def _convert_narrow_to_api_format(narrow: list[NarrowFilter | dict[str, Any]]) -> list[dict[str, Any]]:
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


async def message(
    operation: Literal["send", "schedule", "draft"],
    type: Literal["stream", "private"],
    to: str | list[str],
    content: str,
    topic: str | None = None,
    # Scheduled messaging
    schedule_at: datetime | None = None,
    # Advanced parameters (optional)
    queue_id: str | None = None,  # Event queue association
    local_id: str | None = None,  # Client deduplication
    read_by_sender: bool = True,
    # Formatting options
    syntax_highlight: bool = False,
    link_preview: bool = True,
    emoji_translate: bool = True,
) -> MessageResponse:
    """Send, schedule, or draft messages with full formatting support.

    This consolidated tool replaces send_message with enhanced capabilities including
    scheduled messaging, drafts, and advanced formatting options.

    Args:
        operation: Type of operation - send, schedule, or draft
        type: Message type - stream or private
        to: Recipient(s) - stream name or user email(s)
        content: Message content
        topic: Topic for stream messages (required for stream type)
        schedule_at: When to send scheduled messages (ISO format or datetime)
        queue_id: Event queue ID for message association
        local_id: Client-side ID for deduplication
        read_by_sender: Whether message is marked as read by sender
        syntax_highlight: Enable syntax highlighting for code blocks
        link_preview: Enable automatic link previews
        emoji_translate: Enable emoji code translation

    Returns:
        MessageResponse with status, message_id, and operation details

    Examples:
        # Send immediate message
        await message("send", "stream", "general", "Hello world!", topic="greetings")

        # Schedule message for later
        await message("send", "stream", "announcements", "Meeting reminder",
                     topic="meetings", schedule_at=datetime(2024, 1, 15, 14, 0))

        # Create draft
        await message("draft", "private", "user@example.com", "Draft message")
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.message"}):
        with LogContext(logger, tool="message", operation=operation, type=type, to=str(to)):
            track_tool_call("messaging.message")

            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters based on usage mode
                params = {
                    "operation": operation,
                    "type": type,
                    "to": to,
                    "content": content,
                    "topic": topic,
                    "schedule_at": schedule_at,
                    "queue_id": queue_id,
                    "local_id": local_id,
                    "read_by_sender": read_by_sender,
                    "syntax_highlight": syntax_highlight,
                    "link_preview": link_preview,
                    "emoji_translate": emoji_translate,
                }

                # Remove None values to determine validation mode
                filtered_params = {k: v for k, v in params.items() if v is not None}
                suggested_mode = validator.suggest_mode("messaging.message", filtered_params)
                validated_params = validator.validate_tool_params("messaging.message", params, suggested_mode)

                # Operation-specific validation
                if operation == "schedule" and not schedule_at:
                    return {
                        "status": "error",
                        "error": "schedule_at is required for scheduled messages",
                        "operation": operation
                    }

                if type == "stream" and not topic:
                    return {
                        "status": "error",
                        "error": "Topic is required for stream messages",
                        "operation": operation
                    }

                # Content sanitization and truncation
                safe_content = _truncate_content(content)

                # Select appropriate identity for the operation
                if operation in ["schedule", "draft"]:
                    # These operations typically require bot capabilities
                    preferred_identity = IdentityType.BOT
                else:
                    # Regular send can use current identity
                    preferred_identity = None

                # Execute with appropriate identity and error handling
                async def _execute_message(client, params):
                    if operation == "send":
                        # Immediate send
                        # For private messages Zulip expects a list of recipients
                        if type == "private":
                            recipients = to if isinstance(to, list) else [to]
                        else:
                            recipients = to
                        result = client.send_message(type, recipients, safe_content, topic)

                        if result.get("result") == "success":
                            track_message_sent(type)
                            return {
                                "status": "success",
                                "message_id": result.get("id"),
                                "operation": "send",
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            return {
                                "status": "error",
                                "error": result.get("msg", "Unknown error"),
                                "operation": "send"
                            }

                    elif operation == "schedule":
                        # Scheduled message using Zulip's native API
                        if not schedule_at:
                            return {
                                "status": "error",
                                "error": "schedule_at is required for scheduled messages",
                                "operation": "schedule"
                            }

                        # Create scheduled message instance
                        recipients = [to] if type == "private" else to
                        scheduled_msg = ScheduledMessage(
                            content=safe_content,
                            scheduled_time=schedule_at,
                            message_type=type,
                            recipients=recipients,
                            topic=topic
                        )

                        # Use the scheduler service with current config
                        try:
                            # Create ZulipConfig for scheduler from the current identity
                            # The client wrapper should be a ZulipClientWrapper with config access
                            if hasattr(client, 'config_manager'):
                                # Get the client config that was used to create this client
                                client_config = client.config_manager.get_zulip_client_config(
                                    use_bot=getattr(client, 'use_bot_identity', False)
                                )
                                # Create ZulipConfig from client config
                                from ..config import ZulipConfig
                                scheduler_config = ZulipConfig(
                                    email=client_config["email"],
                                    api_key=client_config["api_key"],
                                    site=client_config["site"]
                                )
                            else:
                                # Fallback: create config from current global config manager
                                fallback_client_config = config.get_zulip_client_config(
                                    use_bot=preferred_identity == IdentityType.BOT
                                )
                                from ..config import ZulipConfig
                                scheduler_config = ZulipConfig(
                                    email=fallback_client_config["email"],
                                    api_key=fallback_client_config["api_key"],
                                    site=fallback_client_config["site"]
                                )

                            # Create scheduler and schedule the message
                            async with MessageScheduler(scheduler_config) as scheduler:
                                result = await scheduler.schedule_message(scheduled_msg)

                            if result.get("result") == "success":
                                track_message_sent(type)
                                return {
                                    "status": "success",
                                    "operation": "schedule",
                                    "scheduled_message_id": result.get("scheduled_message_id"),
                                    "scheduled_at": schedule_at.isoformat(),
                                    "message": "Message scheduled successfully",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            else:
                                return {
                                    "status": "error",
                                    "error": result.get("msg", "Failed to schedule message"),
                                    "operation": "schedule"
                                }

                        except Exception as e:
                            logger.error(f"Error scheduling message: {e}")
                            return {
                                "status": "error",
                                "error": f"Failed to schedule message: {str(e)}",
                                "operation": "schedule"
                            }

                    elif operation == "draft":
                        # Draft message - Zulip doesn't have native draft API, so we'll create a local draft representation
                        # This is appropriate as drafts are typically client-side features
                        draft_id = f"draft_{int(datetime.now().timestamp() * 1000)}"

                        # Create a standardized draft representation
                        draft_data = {
                            "draft_id": draft_id,
                            "type": type,
                            "to": to,
                            "content": safe_content,
                            "topic": topic,
                            "created_at": datetime.now().isoformat(),
                            "last_modified": datetime.now().isoformat()
                        }

                        return {
                            "status": "success",
                            "operation": "draft",
                            "draft_id": draft_id,
                            "draft_data": draft_data,
                            "message": "Draft message created",
                            "note": "Draft stored locally - use draft_data to recreate message when ready to send"
                        }

                result = await identity_manager.execute_with_identity(
                    "messaging.message",
                    validated_params,
                    _execute_message,
                    preferred_identity
                )

                return result

            except Exception as e:
                track_tool_error("messaging.message", _builtins.type(e).__name__)
                logger.error(f"Error in message tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to {operation} message: {str(e)}",
                    "operation": operation
                }


async def search_messages(
    # Simple parameter-based narrow building (NEW - ported from legacy)
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    text: str | None = None,
    # Simple filters (NEW - enhanced beyond legacy)
    has_attachment: bool | None = None,
    has_link: bool | None = None,
    has_image: bool | None = None,
    is_private: bool | None = None,
    is_starred: bool | None = None,
    is_mentioned: bool | None = None,
    # Time-based filters (NEW - enhanced beyond legacy)
    last_hours: int | None = None,
    last_days: int | None = None,
    after_time: datetime | str | None = None,
    before_time: datetime | str | None = None,
    # Advanced narrow support (existing v2.5.0)
    narrow: list[NarrowFilter | dict[str, Any]] | None = None,
    anchor: int | Literal["newest", "oldest", "first_unread"] = "newest",
    num_before: int = 50,
    num_after: int = 50,
    # Advanced options
    include_anchor: bool = True,
    use_first_unread_anchor: bool = False,
    apply_markdown: bool = True,
    client_gravatar: bool = False,
) -> MessageList:
    """Search and retrieve messages with powerful filtering.

    This enhanced tool provides both simple parameter-based filtering (ported from legacy)
    and advanced narrow filtering capabilities for comprehensive message search.

    SIMPLE USAGE (NEW - ported from legacy messaging_simple.py):
        Use basic parameters for common searches:
        - stream, topic, sender, text for content filtering
        - has_attachment, has_link, is_private for content type filtering  
        - last_hours, last_days, after_time for time-based filtering

    ADVANCED USAGE (existing v2.5.0):
        Use narrow parameter for complex filtering with NarrowFilter objects

    Args:
        # Simple parameter-based narrow building
        stream: Stream name to search in
        topic: Topic name to search in
        sender: Sender email to filter by
        text: Text to search for
        has_attachment: Filter for messages with/without attachments
        has_link: Filter for messages with/without links
        has_image: Filter for messages with/without images
        is_private: Filter for private/public messages
        is_starred: Filter for starred/unstarred messages
        is_mentioned: Filter for messages where user is/isn't mentioned
        last_hours: Search in messages from last N hours
        last_days: Search in messages from last N days
        after_time: Search in messages after specific time
        before_time: Search in messages before specific time
        
        # Advanced narrow filtering
        narrow: List of narrow filters for complex filtering (overrides simple params)
        anchor: Starting point - message ID, "newest", "oldest", or "first_unread"
        num_before: Number of messages before anchor
        num_after: Number of messages after anchor
        include_anchor: Whether to include the anchor message
        use_first_unread_anchor: Use first unread as anchor if available
        apply_markdown: Apply markdown rendering to message content
        client_gravatar: Use client-side gravatar rendering

    Returns:
        MessageList with messages, count, and metadata

    Examples:
        # Simple searches (NEW - legacy-compatible)
        await search_messages(stream="general", topic="deployment")
        await search_messages(text="bug fix", last_days=7)
        await search_messages(sender="alice@example.com", has_attachment=True)
        
        # Enhanced simple searches (NEW - beyond legacy)
        await search_messages(
            stream="development", 
            text="docker",
            has_link=True,
            last_hours=24
        )

        # Advanced narrow filtering (existing v2.5.0)
        narrow = [{"operator": "stream", "operand": "general"}]
        await search_messages(narrow=narrow)

        # Using NarrowHelper for complex scenarios (NEW)
        narrow_filters = NarrowHelper.build_basic_narrow(
            stream="engineering",
            text="deployment",
            has_attachment=True,
            last_days=3
        )
        await search_messages(narrow=narrow_filters)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.search_messages"}):
        with LogContext(logger, tool="search_messages", anchor=str(anchor)):
            track_tool_call("messaging.search_messages")

            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "narrow": narrow,
                    "anchor": anchor,
                    "num_before": num_before,
                    "num_after": num_after,
                    "include_anchor": include_anchor,
                    "use_first_unread_anchor": use_first_unread_anchor,
                    "apply_markdown": apply_markdown,
                    "client_gravatar": client_gravatar,
                }

                # Remove None values and determine validation mode
                filtered_params = {k: v for k, v in params.items() if v is not None}
                suggested_mode = validator.suggest_mode("messaging.search_messages", filtered_params)
                validated_params = validator.validate_tool_params("messaging.search_messages", params, suggested_mode)

                # Additional validation
                if isinstance(anchor, int) and anchor <= 0:
                    return {
                        "status": "error",
                        "error": "Invalid message ID for anchor"
                    }

                if num_before < 0 or num_after < 0:
                    return {
                        "status": "error",
                        "error": "num_before and num_after must be non-negative"
                    }

                if num_before + num_after > 5000:
                    return {
                        "status": "error",
                        "error": "Too many messages requested (max 5000)"
                    }

                # Build narrow filters - NEW enhanced logic
                if narrow:
                    # Advanced mode: use provided narrow filters (existing v2.5.0 behavior)
                    api_narrow = _convert_narrow_to_api_format(narrow)
                else:
                    # Simple mode: build from basic parameters (NEW - ported from legacy)
                    simple_params_provided = any([
                        stream, topic, sender, text, has_attachment is not None,
                        has_link is not None, has_image is not None, is_private is not None,
                        is_starred is not None, is_mentioned is not None, last_hours is not None,
                        last_days is not None, after_time is not None, before_time is not None
                    ])
                    
                    if simple_params_provided:
                        # Use enhanced NarrowHelper to build filters
                        narrow_filters = NarrowHelper.build_basic_narrow(
                            stream=stream,
                            topic=topic,
                            sender=sender,
                            text=text,
                            has_attachment=has_attachment,
                            has_link=has_link,
                            has_image=has_image,
                            is_private=is_private,
                            is_starred=is_starred,
                            is_mentioned=is_mentioned,
                            last_hours=last_hours,
                            last_days=last_days,
                            after_time=after_time,
                            before_time=before_time
                        )
                        api_narrow = NarrowHelper.to_api_format(narrow_filters)
                    else:
                        # No filters provided - get all messages
                        api_narrow = []

                # Execute with error handling
                async def _execute_search(client, params):
                    # Get raw response from Zulip
                    request = {
                        "anchor": anchor,
                        "num_before": num_before,
                        "num_after": num_after,
                        "narrow": api_narrow,
                        "include_anchor": include_anchor,
                        "client_gravatar": client_gravatar,
                        "apply_markdown": apply_markdown,
                    }
                    # Use ZulipClientWrapper get_messages_raw for better performance
                    response = client.get_messages_raw(
                        anchor=request["anchor"],
                        num_before=request["num_before"],
                        num_after=request["num_after"],
                        narrow=request["narrow"],
                        include_anchor=request["include_anchor"],
                        client_gravatar=request["client_gravatar"],
                        apply_markdown=request["apply_markdown"]
                    )

                    # Quick validation
                    if response.get("result") != "success":
                        return {
                            "status": "error",
                            "error": response.get("msg", "Failed to get messages"),
                        }

                    # Extract essential fields with optimized dict manipulation
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
                            "flags": msg.get("flags", []),
                            "last_edit_timestamp": msg.get("last_edit_timestamp"),
                        }
                        for msg in response.get("messages", [])
                    ]

                    return {
                        "status": "success",
                        "messages": messages,
                        "count": len(messages),
                        "anchor": response.get("anchor"),
                        "found_anchor": response.get("found_anchor"),
                        "found_newest": response.get("found_newest"),
                        "found_oldest": response.get("found_oldest"),
                        "history_limited": response.get("history_limited"),
                        "narrow": api_narrow,  # Return processed narrow for debugging
                    }

                result = await identity_manager.execute_with_identity(
                    "messaging.search_messages",
                    validated_params,
                    _execute_search
                )

                return result

            except Exception as e:
                track_tool_error("messaging.search_messages", type(e).__name__)
                logger.error(f"Error in search_messages tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to search messages: {str(e)}"
                }


async def edit_message(
    message_id: int,
    content: str | None = None,
    topic: str | None = None,
    stream_id: int | None = None,  # Move between streams
    # Topic propagation control
    propagate_mode: Literal["change_one", "change_later", "change_all"] = "change_one",
    send_notification_to_old_thread: bool = False,
    send_notification_to_new_thread: bool = True,
) -> EditResponse:
    """Edit or move messages with topic management.

    This consolidated tool replaces edit_message with enhanced topic management
    and stream-moving capabilities.

    Args:
        message_id: ID of the message to edit
        content: New message content (optional)
        topic: New topic name (optional)
        stream_id: New stream ID for moving between streams (optional)
        propagate_mode: How to propagate topic changes to other messages
        send_notification_to_old_thread: Send notification to original thread
        send_notification_to_new_thread: Send notification to new thread

    Returns:
        EditResponse with status and operation details

    Examples:
        # Edit message content
        await edit_message(12345, content="Updated message")

        # Change topic and propagate to all messages
        await edit_message(12345, topic="new-topic", propagate_mode="change_all")

        # Move message to different stream
        await edit_message(12345, stream_id=67890, topic="moved-message")
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.edit_message"}):
        with LogContext(logger, tool="edit_message", message_id=message_id):
            track_tool_call("messaging.edit_message")

            try:
                config, identity_manager, validator = _get_managers()

                # Validate parameters
                params = {
                    "message_id": message_id,
                    "content": content,
                    "topic": topic,
                    "stream_id": stream_id,
                    "propagate_mode": propagate_mode,
                    "send_notification_to_old_thread": send_notification_to_old_thread,
                    "send_notification_to_new_thread": send_notification_to_new_thread,
                }

                # Basic parameter validation
                if message_id <= 0:
                    return {
                        "status": "error",
                        "error": "Invalid message ID"
                    }

                if not content and not topic and not stream_id:
                    return {
                        "status": "error",
                        "error": "Must provide content, topic, or stream_id to edit"
                    }

                if content and stream_id:
                    return {
                        "status": "error",
                        "error": "Cannot update content and move stream simultaneously"
                    }

                if propagate_mode not in ["change_one", "change_later", "change_all"]:
                    return {
                        "status": "error",
                        "error": "Invalid propagate_mode"
                    }

                # Content sanitization
                safe_content = _truncate_content(content) if content else None

                # Execute with error handling
                async def _execute_edit(client, params):
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
                        # Determine what changed
                        changes = []
                        if content:
                            changes.append("content")
                        if topic:
                            changes.append("topic")
                        if stream_id:
                            changes.append("stream")

                        return {
                            "status": "success",
                            "message": "Message edited successfully",
                            "message_id": message_id,
                            "changes": changes,
                            "propagate_mode": propagate_mode,
                            "timestamp": datetime.now().isoformat(),
                        }

                    return {
                        "status": "error",
                        "error": result.get("msg", "Failed to edit message"),
                        "message_id": message_id,
                    }

                result = await identity_manager.execute_with_identity(
                    "messaging.edit_message",
                    params,
                    _execute_edit
                )

                return result

            except Exception as e:
                track_tool_error("messaging.edit_message", type(e).__name__)
                logger.error(f"Error in edit_message tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to edit message: {str(e)}",
                    "message_id": message_id,
                }


async def bulk_operations(
    operation: Literal["mark_read", "mark_unread", "add_flag", "remove_flag", "add_reaction", "remove_reaction", "delete_messages"],
    # Simple selection (NEW - ported from legacy messaging_simple.py)
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    # Advanced selection via narrow or IDs (existing v2.5.0)
    narrow: list[NarrowFilter | dict[str, Any]] | None = None,
    message_ids: list[int] | None = None,
    # Operation parameters
    flag: str | None = None,
    # Reaction operations
    emoji_name: str | None = None,
    emoji_code: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] | None = None,
) -> BulkResponse:
    """Bulk message operations with both simple and advanced selection methods.

    This enhanced tool enables bulk operations on multiple messages with
    simple parameter-based selection (ported from legacy) and advanced narrow filtering.

    SIMPLE SELECTION (NEW - ported from legacy messaging_simple.py):
        Use stream, topic, sender parameters for common bulk operations

    ADVANCED SELECTION (existing v2.5.0):
        Use narrow filters or explicit message IDs for complex selection

    Args:
        operation: Type of bulk operation to perform
        
        # Simple selection parameters (NEW)
        stream: Stream name to select messages from
        topic: Topic name to select messages from
        sender: Sender email to select messages from
        
        # Advanced selection parameters (existing)
        narrow: Narrow filters to select messages (overrides simple params)
        message_ids: Explicit list of message IDs (overrides filters)
        
        # Operation-specific parameters
        flag: Flag name for add_flag/remove_flag operations
        emoji_name: Emoji name for reaction operations
        emoji_code: Emoji unicode code for reaction operations
        reaction_type: Type of emoji for reaction operations

    Returns:
        BulkResponse with status, affected count, and operation details

    Examples:
        # Simple selection (NEW - legacy-compatible)
        await bulk_operations("mark_read", stream="general")
        await bulk_operations("mark_read", stream="general", topic="announcements")
        await bulk_operations("add_flag", sender="user@example.com", flag="starred")

        # Advanced selection with narrow filters (existing v2.5.0)
        await bulk_operations("mark_read", narrow=[{"operator": "stream", "operand": "general"}])

        # Explicit message ID selection (existing v2.5.0)
        await bulk_operations("add_flag", message_ids=[123, 456, 789], flag="starred")

        # Reaction operations with simple selection (NEW)
        await bulk_operations("add_reaction", stream="general", emoji_name="thumbs_up")
        await bulk_operations("remove_reaction", topic="deployment", emoji_name="confused")

        # Delete messages with advanced criteria (existing v2.5.0)
        await bulk_operations("delete_messages", narrow=[{"operator": "sender", "operand": "spam@example.com"}])
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.bulk_operations"}):
        with LogContext(logger, tool="bulk_operations", operation=operation):
            track_tool_call("messaging.bulk_operations")

            try:
                config, identity_manager, validator = _get_managers()

                # Enhanced parameter validation with simple selection support
                simple_params_provided = any([stream, topic, sender])
                
                # Count selection methods
                selection_methods = sum([
                    bool(narrow),
                    bool(message_ids),
                    simple_params_provided
                ])
                
                if selection_methods == 0:
                    return {
                        "status": "error",
                        "error": "Must provide message selection: use stream/topic/sender, narrow filters, or message_ids"
                    }

                if selection_methods > 1:
                    return {
                        "status": "error",
                        "error": "Cannot specify multiple selection methods: choose one of simple params, narrow, or message_ids"
                    }

                if operation in ["add_flag", "remove_flag"] and not flag:
                    return {
                        "status": "error",
                        "error": f"Flag parameter is required for {operation}"
                    }

                if operation in ["add_reaction", "remove_reaction"] and not emoji_name:
                    return {
                        "status": "error",
                        "error": f"emoji_name parameter is required for {operation}"
                    }

                # Build selection method with enhanced logic (NEW - ported from legacy)
                if message_ids:
                    # Explicit message ID selection (existing v2.5.0)
                    selection_narrow = None
                elif narrow:
                    # Advanced narrow selection (existing v2.5.0)
                    selection_narrow = _convert_narrow_to_api_format(narrow)
                else:
                    # Simple parameter selection (NEW - ported from legacy)
                    narrow_filters = build_basic_narrow(
                        stream=stream,
                        topic=topic,
                        sender=sender
                    )
                    selection_narrow = NarrowHelper.to_api_format(narrow_filters)

                # Execute with error handling
                async def _execute_bulk_op(client, params):
                    if operation in ["mark_read", "mark_unread"]:
                        # Use update_message_flags for read/unread operations
                        if selection_narrow:
                            # Get messages matching narrow first
                            search_request = {
                                "anchor": "newest",
                                "num_before": 1000,  # Reasonable limit for bulk ops
                                "num_after": 0,
                                "narrow": selection_narrow,
                            }
                            search_response = client.get_messages_raw(
                                anchor=search_request["anchor"],
                                num_before=search_request["num_before"],
                                num_after=search_request["num_after"],
                                narrow=search_request["narrow"]
                            )

                            if search_response.get("result") != "success":
                                return {
                                    "status": "error",
                                    "error": f"Failed to find messages: {search_response.get('msg')}"
                                }

                            target_ids = [msg["id"] for msg in search_response.get("messages", [])]
                        else:
                            target_ids = message_ids

                        if not target_ids:
                            return {
                                "status": "success",
                                "message": "No messages matched the criteria",
                                "affected_count": 0,
                                "operation": operation
                            }

                        # Execute read/unread operation
                        flag_name = "read"
                        op = "add" if operation == "mark_read" else "remove"

                        result = client.update_message_flags(
                            messages=target_ids,
                            op=op,
                            flag=flag_name
                        )

                        if result.get("result") == "success":
                            return {
                                "status": "success",
                                "message": f"Successfully {operation.replace('_', ' ')}",
                                "affected_count": len(target_ids),
                                "operation": operation,
                                "message_ids": target_ids[:10],  # Return first 10 IDs for reference
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            return {
                                "status": "error",
                                "error": result.get("msg", f"Failed to {operation}"),
                                "operation": operation
                            }

                    elif operation in ["add_flag", "remove_flag"]:
                        # Handle flag operations
                        if selection_narrow:
                            # Get messages matching narrow first
                            search_request = {
                                "anchor": "newest",
                                "num_before": 1000,  # Reasonable limit for bulk ops
                                "num_after": 0,
                                "narrow": selection_narrow,
                            }
                            search_response = client.get_messages_raw(
                                anchor=search_request["anchor"],
                                num_before=search_request["num_before"],
                                num_after=search_request["num_after"],
                                narrow=search_request["narrow"]
                            )

                            if search_response.get("result") != "success":
                                return {
                                    "status": "error",
                                    "error": f"Failed to find messages: {search_response.get('msg')}"
                                }

                            target_ids = [msg["id"] for msg in search_response.get("messages", [])]
                        else:
                            target_ids = message_ids

                        if not target_ids:
                            return {
                                "status": "success",
                                "message": "No messages matched the criteria",
                                "affected_count": 0,
                                "operation": operation,
                                "flag": flag
                            }

                        # Execute flag operation
                        op = "add" if operation == "add_flag" else "remove"

                        result = client.update_message_flags(
                            messages=target_ids,
                            op=op,
                            flag=flag
                        )

                        if result.get("result") == "success":
                            return {
                                "status": "success",
                                "message": f"Successfully {operation.replace('_', ' ')} '{flag}'",
                                "affected_count": len(target_ids),
                                "operation": operation,
                                "flag": flag,
                                "message_ids": target_ids[:10],  # Return first 10 IDs for reference
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            return {
                                "status": "error",
                                "error": result.get("msg", f"Failed to {operation}"),
                                "operation": operation,
                                "flag": flag
                            }

                    elif operation in ["add_reaction", "remove_reaction"]:
                        # Handle reaction operations
                        if selection_narrow:
                            # Get messages matching narrow first
                            search_request = {
                                "anchor": "newest",
                                "num_before": 1000,  # Reasonable limit for bulk ops
                                "num_after": 0,
                                "narrow": selection_narrow,
                            }
                            search_response = client.get_messages_raw(
                                anchor=search_request["anchor"],
                                num_before=search_request["num_before"],
                                num_after=search_request["num_after"],
                                narrow=search_request["narrow"]
                            )

                            if search_response.get("result") != "success":
                                return {
                                    "status": "error",
                                    "error": f"Failed to find messages: {search_response.get('msg')}"
                                }

                            target_ids = [msg["id"] for msg in search_response.get("messages", [])]
                        else:
                            target_ids = message_ids

                        if not target_ids:
                            return {
                                "status": "success",
                                "message": "No messages matched the criteria",
                                "affected_count": 0,
                                "operation": operation,
                                "emoji_name": emoji_name
                            }

                        # Execute reaction operation on each message
                        successful_reactions = []
                        failed_reactions = []
                        
                        for message_id in target_ids:
                            try:
                                if operation == "add_reaction":
                                    result = client.add_reaction(message_id, emoji_name)
                                else:  # remove_reaction
                                    result = client.remove_reaction(message_id, emoji_name)

                                if result.get("result") == "success":
                                    successful_reactions.append(message_id)
                                else:
                                    failed_reactions.append({
                                        "message_id": message_id,
                                        "error": result.get("msg", "Unknown error")
                                    })
                            except Exception as e:
                                failed_reactions.append({
                                    "message_id": message_id,
                                    "error": str(e)
                                })

                        return {
                            "status": "success" if successful_reactions else "partial_success",
                            "message": f"Successfully {operation.replace('_', ' ')} '{emoji_name}'",
                            "affected_count": len(successful_reactions),
                            "successful_reactions": successful_reactions[:10],  # Return first 10 IDs
                            "failed_reactions": failed_reactions[:5],  # Return first 5 failures
                            "operation": operation,
                            "emoji_name": emoji_name,
                            "timestamp": datetime.now().isoformat(),
                        }

                    elif operation == "delete_messages":
                        # Handle message deletion
                        if selection_narrow:
                            # Get messages matching narrow first
                            search_request = {
                                "anchor": "newest",
                                "num_before": 1000,  # Reasonable limit for bulk ops
                                "num_after": 0,
                                "narrow": selection_narrow,
                            }
                            search_response = client.get_messages_raw(
                                anchor=search_request["anchor"],
                                num_before=search_request["num_before"],
                                num_after=search_request["num_after"],
                                narrow=search_request["narrow"]
                            )

                            if search_response.get("result") != "success":
                                return {
                                    "status": "error",
                                    "error": f"Failed to find messages: {search_response.get('msg')}"
                                }

                            target_ids = [msg["id"] for msg in search_response.get("messages", [])]
                        else:
                            target_ids = message_ids

                        if not target_ids:
                            return {
                                "status": "success",
                                "message": "No messages matched the criteria",
                                "affected_count": 0,
                                "operation": operation
                            }

                        # Execute deletion on each message
                        successful_deletions = []
                        failed_deletions = []
                        
                        for message_id in target_ids:
                            try:
                                result = client.delete_message(message_id)
                                if result.get("result") == "success":
                                    successful_deletions.append(message_id)
                                else:
                                    failed_deletions.append({
                                        "message_id": message_id,
                                        "error": result.get("msg", "Unknown error")
                                    })
                            except Exception as e:
                                failed_deletions.append({
                                    "message_id": message_id,
                                    "error": str(e)
                                })

                        return {
                            "status": "success" if successful_deletions else "partial_success",
                            "message": f"Successfully deleted {len(successful_deletions)} messages",
                            "affected_count": len(successful_deletions),
                            "successful_deletions": successful_deletions[:10],  # Return first 10 IDs
                            "failed_deletions": failed_deletions[:5],  # Return first 5 failures
                            "operation": operation,
                            "timestamp": datetime.now().isoformat(),
                        }

                    else:
                        return {
                            "status": "error",
                            "error": f"Unsupported operation: {operation}"
                        }

                result = await identity_manager.execute_with_identity(
                    "messaging.bulk_operations",
                    {"operation": operation, "narrow": selection_narrow, "message_ids": message_ids, "flag": flag},
                    _execute_bulk_op
                )

                return result

            except Exception as e:
                track_tool_error("messaging.bulk_operations", type(e).__name__)
                logger.error(f"Error in bulk_operations tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to perform bulk operation: {str(e)}",
                    "operation": operation
                }


async def message_history(
    message_id: int,
    include_content_history: bool = True,
    include_edit_history: bool = True,
    include_reaction_history: bool = False,
) -> dict[str, Any]:
    """Get comprehensive message history and edit tracking.

    This tool provides detailed history information for a specific message,
    including content changes, edit timestamps, and reaction history.

    Args:
        message_id: ID of the message to get history for
        include_content_history: Include previous versions of message content
        include_edit_history: Include edit timestamps and user information
        include_reaction_history: Include reaction addition/removal history

    Returns:
        Dictionary with comprehensive message history

    Examples:
        # Get full message history
        await message_history(12345, include_content_history=True, include_edit_history=True)

        # Get only edit history
        await message_history(12345, include_content_history=False, include_edit_history=True)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.message_history"}):
        with LogContext(logger, tool="message_history", message_id=message_id):
            track_tool_call("messaging.message_history")

            try:
                config, identity_manager, validator = _get_managers()

                # Parameter validation
                if message_id <= 0:
                    return {
                        "status": "error",
                        "error": "Invalid message ID"
                    }

                # Execute with error handling
                async def _execute_history(client, params):
                    # Get message details first
                    message_result = client.get_message(message_id)
                    if message_result.get("result") != "success":
                        return {
                            "status": "error",
                            "error": f"Message not found: {message_result.get('msg', 'Unknown error')}"
                        }

                    message = message_result.get("message", {})
                    
                    history_data = {
                        "status": "success",
                        "message_id": message_id,
                        "original_timestamp": message.get("timestamp"),
                        "sender": message.get("sender_full_name"),
                        "sender_email": message.get("sender_email"),
                        "current_content": _truncate_content(message.get("content", "")),
                        "stream_id": message.get("stream_id"),
                        "topic": message.get("subject"),
                    }

                    # Include edit history if requested
                    if include_edit_history:
                        edit_history = []
                        if message.get("last_edit_timestamp"):
                            edit_history.append({
                                "timestamp": message.get("last_edit_timestamp"),
                                "edit_type": "content_or_topic_change",
                                "note": "Message was edited (specific changes not available via API)"
                            })
                        
                        history_data["edit_history"] = edit_history
                        history_data["total_edits"] = len(edit_history)

                    # Include content history if requested (limited by API)
                    if include_content_history:
                        history_data["content_history"] = {
                            "note": "Full content history not available via Zulip API",
                            "current_version": _truncate_content(message.get("content", "")),
                            "has_been_edited": bool(message.get("last_edit_timestamp"))
                        }

                    # Include reaction history if requested
                    if include_reaction_history:
                        reactions = message.get("reactions", [])
                        history_data["reaction_history"] = {
                            "current_reactions": reactions,
                            "total_reactions": sum(len(r.get("user_id", [])) for r in reactions),
                            "reaction_types": list(set(r.get("emoji_name") for r in reactions)),
                            "note": "Detailed reaction history not available via API"
                        }

                    return history_data

                result = await identity_manager.execute_with_identity(
                    "messaging.message_history",
                    {"message_id": message_id},
                    _execute_history
                )

                return result

            except Exception as e:
                track_tool_error("messaging.message_history", type(e).__name__)
                logger.error(f"Error in message_history tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to get message history: {str(e)}",
                    "message_id": message_id
                }


async def cross_post_message(
    source_message_id: int,
    target_streams: list[str],
    target_topic: str | None = None,
    add_reference: bool = True,
    custom_prefix: str | None = None,
) -> dict[str, Any]:
    """Cross-post messages between streams.

    This tool enables sharing messages across multiple streams with optional
    reference back to the original message.

    Args:
        source_message_id: ID of the original message to cross-post
        target_streams: List of stream names to post to
        target_topic: Topic for cross-posted messages (uses original if None)
        add_reference: Add reference link to original message
        custom_prefix: Custom prefix text for cross-posted messages

    Returns:
        Dictionary with cross-posting results

    Examples:
        # Cross-post to multiple streams
        await cross_post_message(
            12345,
            ["general", "announcements"],
            target_topic="Important Update",
            add_reference=True
        )

        # Cross-post with custom prefix
        await cross_post_message(
            12345,
            ["team-updates"],
            custom_prefix="FYI from #general:"
        )
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.cross_post_message"}):
        with LogContext(logger, tool="cross_post_message", message_id=source_message_id):
            track_tool_call("messaging.cross_post_message")

            try:
                config, identity_manager, validator = _get_managers()

                # Parameter validation
                if source_message_id <= 0:
                    return {
                        "status": "error",
                        "error": "Invalid source message ID"
                    }

                if not target_streams:
                    return {
                        "status": "error",
                        "error": "At least one target stream is required"
                    }

                # Execute with error handling
                async def _execute_cross_post(client, params):
                    # Get source message first
                    message_result = client.get_message(source_message_id)
                    if message_result.get("result") != "success":
                        return {
                            "status": "error",
                            "error": f"Source message not found: {message_result.get('msg', 'Unknown error')}"
                        }

                    source_message = message_result.get("message", {})
                    original_content = source_message.get("content", "")
                    original_topic = target_topic or source_message.get("subject", "Cross-post")
                    original_stream = source_message.get("display_recipient", "unknown")
                    
                    # Prepare cross-post content
                    prefix = custom_prefix or f"Cross-posted from #{original_stream}:"
                    
                    cross_post_content = f"{prefix}\n\n{original_content}"
                    
                    if add_reference:
                        # Add reference link (simplified)
                        reference_link = f"\n\n_Original message: #{original_stream} > {source_message.get('subject', 'topic')}_"
                        cross_post_content += reference_link

                    # Cross-post to each target stream
                    results = []
                    successful_posts = []
                    failed_posts = []

                    for stream_name in target_streams:
                        try:
                            post_result = client.send_message(
                                "stream",
                                stream_name,
                                _truncate_content(cross_post_content),
                                original_topic
                            )

                            if post_result.get("result") == "success":
                                successful_posts.append({
                                    "stream": stream_name,
                                    "topic": original_topic,
                                    "message_id": post_result.get("id"),
                                    "status": "success"
                                })
                            else:
                                failed_posts.append({
                                    "stream": stream_name,
                                    "error": post_result.get("msg", "Unknown error"),
                                    "status": "error"
                                })
                        except Exception as e:
                            failed_posts.append({
                                "stream": stream_name,
                                "error": str(e),
                                "status": "error"
                            })

                    return {
                        "status": "success" if successful_posts else "error",
                        "source_message_id": source_message_id,
                        "successful_posts": successful_posts,
                        "failed_posts": failed_posts,
                        "total_attempted": len(target_streams),
                        "total_successful": len(successful_posts),
                        "total_failed": len(failed_posts),
                        "timestamp": datetime.now().isoformat(),
                    }

                result = await identity_manager.execute_with_identity(
                    "messaging.cross_post_message",
                    {"source_message_id": source_message_id},
                    _execute_cross_post
                )

                return result

            except Exception as e:
                track_tool_error("messaging.cross_post_message", type(e).__name__)
                logger.error(f"Error in cross_post_message tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to cross-post message: {str(e)}",
                    "source_message_id": source_message_id
                }


async def add_reaction(
    message_id: int,
    emoji_name: str,
    emoji_code: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Add emoji reaction to a message.

    Simple standalone function to add a single reaction to a message.
    This provides the familiar single-message reaction interface that users expect.

    Args:
        message_id: ID of the message to add reaction to
        emoji_name: Name of the emoji (e.g., "thumbs_up", "heart")
        emoji_code: Unicode code for the emoji (optional, defaults to emoji_name)
        reaction_type: Type of emoji - unicode_emoji, realm_emoji, or zulip_extra_emoji

    Returns:
        Response with status and operation details

    Examples:
        # Add thumbs up reaction
        await add_reaction(12345, "thumbs_up")

        # Add custom realm emoji
        await add_reaction(12345, "custom_emoji", reaction_type="realm_emoji")

        # Add with specific emoji code
        await add_reaction(12345, "heart", emoji_code="2764")
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.add_reaction"}):
        with LogContext(logger, tool="add_reaction", message_id=message_id, emoji=emoji_name):
            track_tool_call("messaging.add_reaction")

            try:
                config, identity_manager, validator = _get_managers()

                # Parameter validation
                if message_id <= 0:
                    return {
                        "status": "error",
                        "error": "Invalid message ID"
                    }

                if not validate_emoji(emoji_name):
                    return {
                        "status": "error",
                        "error": "Invalid emoji name"
                    }

                if reaction_type not in ["unicode_emoji", "realm_emoji", "zulip_extra_emoji"]:
                    return {
                        "status": "error",
                        "error": "Invalid reaction_type. Must be unicode_emoji, realm_emoji, or zulip_extra_emoji"
                    }

                # Execute with identity management and error handling
                async def _execute_add_reaction(client, params):
                    # Use the ZulipClientWrapper add_reaction method
                    result = client.add_reaction(message_id, emoji_name)

                    if result.get("result") == "success":
                        return {
                            "status": "success",
                            "message": "Reaction added successfully",
                            "message_id": message_id,
                            "emoji_name": emoji_name,
                            "reaction_type": reaction_type,
                            "timestamp": datetime.now().isoformat(),
                        }
                    else:
                        return {
                            "status": "error",
                            "error": result.get("msg", "Failed to add reaction"),
                            "message_id": message_id,
                            "emoji_name": emoji_name,
                        }

                result = await identity_manager.execute_with_identity(
                    "messaging.add_reaction",
                    {"message_id": message_id, "emoji_name": emoji_name},
                    _execute_add_reaction
                )

                return result

            except Exception as e:
                track_tool_error("messaging.add_reaction", _builtins.type(e).__name__)
                logger.error(f"Error in add_reaction tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to add reaction: {str(e)}",
                    "message_id": message_id,
                    "emoji_name": emoji_name,
                }


async def remove_reaction(
    message_id: int,
    emoji_name: str,
    emoji_code: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Remove emoji reaction from a message.

    Simple standalone function to remove a single reaction from a message.
    This provides the familiar single-message reaction interface that users expect.

    Args:
        message_id: ID of the message to remove reaction from
        emoji_name: Name of the emoji (e.g., "thumbs_up", "heart")
        emoji_code: Unicode code for the emoji (optional, defaults to emoji_name)
        reaction_type: Type of emoji - unicode_emoji, realm_emoji, or zulip_extra_emoji

    Returns:
        Response with status and operation details

    Examples:
        # Remove thumbs up reaction
        await remove_reaction(12345, "thumbs_up")

        # Remove custom realm emoji
        await remove_reaction(12345, "custom_emoji", reaction_type="realm_emoji")

        # Remove with specific emoji code
        await remove_reaction(12345, "heart", emoji_code="2764")
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "messaging.remove_reaction"}):
        with LogContext(logger, tool="remove_reaction", message_id=message_id, emoji=emoji_name):
            track_tool_call("messaging.remove_reaction")

            try:
                config, identity_manager, validator = _get_managers()

                # Parameter validation
                if message_id <= 0:
                    return {
                        "status": "error",
                        "error": "Invalid message ID"
                    }

                if not validate_emoji(emoji_name):
                    return {
                        "status": "error",
                        "error": "Invalid emoji name"
                    }

                if reaction_type not in ["unicode_emoji", "realm_emoji", "zulip_extra_emoji"]:
                    return {
                        "status": "error",
                        "error": "Invalid reaction_type. Must be unicode_emoji, realm_emoji, or zulip_extra_emoji"
                    }

                # Execute with identity management and error handling
                async def _execute_remove_reaction(client, params):
                    # Use the ZulipClientWrapper remove_reaction method
                    result = client.remove_reaction(message_id, emoji_name)

                    if result.get("result") == "success":
                        return {
                            "status": "success",
                            "message": "Reaction removed successfully",
                            "message_id": message_id,
                            "emoji_name": emoji_name,
                            "reaction_type": reaction_type,
                            "timestamp": datetime.now().isoformat(),
                        }
                    else:
                        return {
                            "status": "error",
                            "error": result.get("msg", "Failed to remove reaction"),
                            "message_id": message_id,
                            "emoji_name": emoji_name,
                        }

                result = await identity_manager.execute_with_identity(
                    "messaging.remove_reaction",
                    {"message_id": message_id, "emoji_name": emoji_name},
                    _execute_remove_reaction
                )

                return result

            except Exception as e:
                track_tool_error("messaging.remove_reaction", _builtins.type(e).__name__)
                logger.error(f"Error in remove_reaction tool: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to remove reaction: {str(e)}",
                    "message_id": message_id,
                    "emoji_name": emoji_name,
                }


def register_messaging_v25_tools(mcp: Any) -> None:
    """Register v2.5.0 consolidated messaging tools on the given MCP instance.

    Registers the 8 consolidated messaging tools:
    - message: Send, schedule, or draft messages
    - search_messages: Search and retrieve messages with powerful filtering
    - edit_message: Edit or move messages with topic management
    - bulk_operations: Bulk message operations including reactions, flags, and deletion
    - message_history: Get comprehensive message history and edit tracking
    - cross_post_message: Cross-post messages between streams
    - add_reaction: Add emoji reaction to a single message (standalone)
    - remove_reaction: Remove emoji reaction from a single message (standalone)

    Args:
        mcp: FastMCP instance to register tools on
    """
    # Register tools with comprehensive descriptions
    mcp.tool(
        description="Send, schedule, or draft messages with full formatting support and advanced options"
    )(message)

    mcp.tool(
        description="Search and retrieve messages with powerful filtering using narrow operators and advanced options"
    )(search_messages)

    mcp.tool(
        description="Edit or move messages with comprehensive topic management and stream transfer capabilities"
    )(edit_message)

    mcp.tool(
        description="Perform bulk operations on multiple messages including reactions, flags, and deletion"
    )(bulk_operations)

    mcp.tool(
        description="Get comprehensive message history and edit tracking information"
    )(message_history)

    mcp.tool(
        description="Cross-post messages between streams with optional reference links"
    )(cross_post_message)

    # Standalone reaction management functions
    mcp.tool(
        description="Add emoji reaction to a single message - simple standalone interface"
    )(add_reaction)

    mcp.tool(
        description="Remove emoji reaction from a single message - simple standalone interface"
    )(remove_reaction)

    logger.info("Registered 8 consolidated messaging v2.5.0 tools")


# Legacy compatibility functions for migration
def get_legacy_send_message():
    """Get legacy send_message function for migration compatibility."""
    async def legacy_send_message(message_type: str, to: str, content: str, topic: str = None):
        return await message("send", message_type, to, content, topic=topic)
    return legacy_send_message


def get_legacy_get_messages():
    """Get legacy get_messages function for migration compatibility."""
    async def legacy_get_messages(
        anchor="newest",
        num_before=0,
        num_after=100,
        narrow=None,
        include_anchor=True,
        client_gravatar=True,
        apply_markdown=True,
    ):
        return await search_messages(
            narrow=narrow or [],
            anchor=anchor,
            num_before=num_before,
            num_after=num_after,
            include_anchor=include_anchor,
            client_gravatar=client_gravatar,
            apply_markdown=apply_markdown,
        )
    return legacy_get_messages


def get_legacy_edit_message():
    """Get legacy edit_message function for migration compatibility."""
    async def legacy_edit_message(
        message_id: int,
        content: str = None,
        topic: str = None,
        propagate_mode: str = "change_one",
        send_notification_to_old_thread: bool = False,
        send_notification_to_new_thread: bool = True,
        stream_id: int = None,
    ):
        return await edit_message(
            message_id=message_id,
            content=content,
            topic=topic,
            stream_id=stream_id,
            propagate_mode=propagate_mode,
            send_notification_to_old_thread=send_notification_to_old_thread,
            send_notification_to_new_thread=send_notification_to_new_thread,
        )
    return legacy_edit_message
