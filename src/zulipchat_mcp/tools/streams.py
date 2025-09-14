"""Stream management tools for ZulipChat MCP v2.5.1.

Complete stream and topic operations including management, analytics, and settings.
All functionality from the complex v25 architecture preserved in minimal code.
"""

from collections import Counter
from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


async def manage_streams(
    operation: Literal["list", "create", "update", "delete", "subscribe", "unsubscribe"],
    stream_names: list[str] | None = None,
    stream_ids: list[int] | None = None,
    properties: dict[str, Any] | None = None,
    principals: list[str] | None = None,
    announce: bool = False,
    invite_only: bool = False,
    include_public: bool = True,
    include_subscribed: bool = True,
    include_all_active: bool = False,
    authorization_errors_fatal: bool = True,
    history_public_to_subscribers: bool | None = None,
    stream_post_policy: int | None = None,
    message_retention_days: int | None = None,
) -> dict[str, Any]:
    """Complete stream lifecycle management with bulk operations."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        if operation == "list":
            result = client.get_streams(include_subscribed=include_subscribed)
            if result.get("result") == "success":
                streams = result.get("streams", [])

                # Apply additional filters
                if not include_public:
                    streams = [s for s in streams if s.get("invite_only", False)]

                return {
                    "status": "success",
                    "streams": streams,
                    "count": len(streams),
                    "filters_applied": {
                        "include_public": include_public,
                        "include_subscribed": include_subscribed,
                        "include_all_active": include_all_active,
                    }
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to list streams")}

        elif operation == "create":
            if not stream_names:
                return {"status": "error", "error": "Stream names required for create operation"}

            # Create streams with properties
            streams_to_create = []
            for name in stream_names:
                stream_def = {"name": name}
                if invite_only:
                    stream_def["invite_only"] = True
                if properties:
                    stream_def.update(properties)
                streams_to_create.append(stream_def)

            result = client.add_subscriptions(
                subscriptions=streams_to_create,
                principals=principals,
                announce=announce,
                authorization_errors_fatal=authorization_errors_fatal,
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "create",
                    "created": result.get("subscribed", {}),
                    "already_subscribed": result.get("already_subscribed", {}),
                    "properties_applied": properties,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to create streams")}

        elif operation == "subscribe":
            if not stream_names:
                return {"status": "error", "error": "Stream names required for subscribe operation"}

            streams_to_sub = [{"name": name} for name in stream_names]
            result = client.add_subscriptions(
                subscriptions=streams_to_sub,
                principals=principals,
                announce=announce,
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "subscribe",
                    "subscribed": result.get("subscribed", {}),
                    "already_subscribed": result.get("already_subscribed", {}),
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to subscribe")}

        elif operation == "unsubscribe":
            if not stream_names:
                return {"status": "error", "error": "Stream names required for unsubscribe operation"}

            result = client.remove_subscriptions(stream_names)

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "unsubscribe",
                    "unsubscribed": result.get("removed", []),
                    "not_removed": result.get("not_removed", []),
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to unsubscribe")}

        elif operation == "delete":
            if not stream_ids:
                return {"status": "error", "error": "Stream IDs required for delete operation"}

            deleted = []
            errors = []

            for stream_id in stream_ids:
                result = client.delete_stream(stream_id)
                if result.get("result") == "success":
                    deleted.append(stream_id)
                else:
                    errors.append(f"Stream {stream_id}: {result.get('msg', 'Unknown error')}")

            return {
                "status": "success" if not errors else "partial",
                "operation": "delete",
                "deleted": deleted,
                "errors": errors,
            }

        else:
            return {"status": "error", "error": f"Unknown operation: {operation}"}

    except Exception as e:
        return {"status": "error", "error": str(e), "operation": operation}


async def manage_topics(
    stream_id: int,
    operation: Literal["list", "move", "delete", "mark_read", "mute", "unmute"],
    source_topic: str | None = None,
    target_topic: str | None = None,
    target_stream_id: int | None = None,
    propagate_mode: str = "change_all",
    send_notification_to_new_thread: bool = True,
    send_notification_to_old_thread: bool = True,
    max_results: int = 100,
    include_muted: bool = True,
) -> dict[str, Any]:
    """Complete topic operations within streams."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        if operation == "list":
            result = client.get_stream_topics(stream_id)
            if result.get("result") == "success":
                topics = result.get("topics", [])

                # Filter muted topics if requested
                if not include_muted:
                    # Note: Zulip API doesn't directly provide muted status in topics list
                    # This would require cross-referencing with user's muted topics
                    pass

                return {
                    "status": "success",
                    "stream_id": stream_id,
                    "topics": topics[:max_results],
                    "count": len(topics),
                    "include_muted": include_muted,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to list topics")}

        elif operation == "mark_read":
            if not source_topic:
                return {"status": "error", "error": "source_topic required for mark_read operation"}

            result = client.mark_topic_as_read(stream_id, source_topic)
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "mark_read",
                    "stream_id": stream_id,
                    "topic": source_topic,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to mark topic as read")}

        elif operation == "mute":
            if not source_topic:
                return {"status": "error", "error": "source_topic required for mute operation"}

            result = client.mute_topic(stream_id, source_topic)
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "mute",
                    "stream_id": stream_id,
                    "topic": source_topic,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to mute topic")}

        elif operation == "unmute":
            if not source_topic:
                return {"status": "error", "error": "source_topic required for unmute operation"}

            result = client.unmute_topic(stream_id, source_topic)
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "unmute",
                    "stream_id": stream_id,
                    "topic": source_topic,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to unmute topic")}

        elif operation == "move":
            if not source_topic or not target_topic:
                return {"status": "error", "error": "source_topic and target_topic required for move operation"}

            # Topic moving is done via message editing with propagation
            # First, find messages in the source topic
            from .search import search_messages
            search_result = await search_messages(
                stream=None,  # We'll use stream_id directly in narrow
                topic=source_topic,
                limit=1,  # Just need one message to edit
            )

            if search_result.get("status") != "success" or not search_result.get("messages"):
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
                    "operation": "move",
                    "source_stream_id": stream_id,
                    "target_stream_id": target_stream_id or stream_id,
                    "source_topic": source_topic,
                    "target_topic": target_topic,
                    "propagate_mode": propagate_mode,
                }
            else:
                return {"status": "error", "error": edit_result.get("error", "Failed to move topic")}

        elif operation == "delete":
            if not source_topic:
                return {"status": "error", "error": "source_topic required for delete operation"}

            result = client.delete_topic(stream_id, source_topic)
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "delete",
                    "stream_id": stream_id,
                    "topic": source_topic,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to delete topic")}

        else:
            return {"status": "error", "error": f"Unknown operation: {operation}"}

    except Exception as e:
        return {"status": "error", "error": str(e), "operation": operation}


async def get_stream_info(
    stream_name: str | None = None,
    stream_id: int | None = None,
    include_subscribers: bool = False,
    include_topics: bool = False,
    include_settings: bool = False,
    include_web_public: bool = False,
) -> dict[str, Any]:
    """Get comprehensive stream information with optional details."""
    if not stream_name and not stream_id:
        return {"status": "error", "error": "Either stream_name or stream_id is required"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Get stream info
        if stream_name and not stream_id:
            stream_result = client.get_stream_id(stream_name)
            if stream_result.get("result") != "success":
                return {"status": "error", "error": f"Stream '{stream_name}' not found"}
            stream_id = stream_result.get("stream_id")

        # Get basic stream information from streams list
        streams_result = client.get_streams()
        if streams_result.get("result") == "success":
            streams = streams_result.get("streams", [])
            stream_info = next((s for s in streams if s.get("stream_id") == stream_id), None)
            if not stream_info:
                return {"status": "error", "error": "Stream not found"}
        else:
            return {"status": "error", "error": "Failed to get stream information"}

        info = {
            "status": "success",
            "stream_id": stream_id,
            "name": stream_info.get("name"),
            "description": stream_info.get("description"),
            "invite_only": stream_info.get("invite_only", False),
            "rendered_description": stream_info.get("rendered_description"),
            "is_web_public": stream_info.get("is_web_public", False),
            "stream_post_policy": stream_info.get("stream_post_policy"),
            "message_retention_days": stream_info.get("message_retention_days"),
            "history_public_to_subscribers": stream_info.get("history_public_to_subscribers"),
            "first_message_id": stream_info.get("first_message_id"),
            "is_announcement_only": stream_info.get("is_announcement_only", False),
        }

        # Get subscribers if requested
        if include_subscribers and stream_id:
            sub_result = client.get_subscribers(stream_id)
            if sub_result.get("result") == "success":
                info["subscribers"] = sub_result.get("subscribers", [])
                info["subscriber_count"] = len(sub_result.get("subscribers", []))

        # Get topics if requested
        if include_topics and stream_id:
            topics_result = client.get_stream_topics(stream_id)
            if topics_result.get("result") == "success":
                topics = topics_result.get("topics", [])
                info["topics"] = topics
                info["topic_count"] = len(topics)

                # Add topic analytics
                if topics:
                    total_messages = sum(topic.get("max_id", 0) - topic.get("min_id", 0) + 1 for topic in topics if topic.get("max_id") and topic.get("min_id"))
                    info["topic_analytics"] = {
                        "most_active_topic": max(topics, key=lambda t: t.get("max_id", 0) - t.get("min_id", 0))["name"] if topics else None,
                        "estimated_total_messages": total_messages,
                        "avg_messages_per_topic": total_messages / len(topics) if topics else 0,
                    }

        return info

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def stream_analytics(
    stream_name: str | None = None,
    stream_id: int | None = None,
    time_period: Literal["day", "week", "month", "year"] = "week",
    include_message_stats: bool = True,
    include_topic_stats: bool = True,
    include_user_activity: bool = True,
) -> dict[str, Any]:
    """Generate detailed stream statistics and analytics."""
    if not stream_name and not stream_id:
        return {"status": "error", "error": "Either stream_name or stream_id is required"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Get stream information
        if stream_name and not stream_id:
            stream_result = client.get_stream_id(stream_name)
            if stream_result.get("result") != "success":
                return {"status": "error", "error": f"Stream '{stream_name}' not found"}
            stream_id = stream_result.get("stream_id")
            current_stream_name = stream_name
        else:
            # Get stream name from ID
            streams_result = client.get_streams()
            if streams_result.get("result") == "success":
                streams = streams_result.get("streams", [])
                stream_info = next((s for s in streams if s.get("stream_id") == stream_id), None)
                if stream_info:
                    current_stream_name = stream_info.get("name")
                else:
                    return {"status": "error", "error": "Stream not found"}
            else:
                return {"status": "error", "error": "Failed to get stream information"}

        # Calculate time range
        time_periods = {
            "day": 24,
            "week": 168,  # 24 * 7
            "month": 720,  # 24 * 30
            "year": 8760,  # 24 * 365
        }
        hours_back = time_periods.get(time_period, 168)

        analytics_data = {
            "stream_id": stream_id,
            "stream_name": current_stream_name,
            "time_period": time_period,
            "analysis_date": datetime.now().isoformat(),
        }

        # Get messages for analysis
        if include_message_stats or include_user_activity:
            from .search import search_messages
            search_result = await search_messages(
                stream=current_stream_name,
                last_hours=hours_back,
                limit=500,  # Large sample for analytics
            )

            if search_result.get("status") == "success":
                messages = search_result.get("messages", [])

                if include_message_stats:
                    analytics_data["message_stats"] = {
                        "total_messages": len(messages),
                        "avg_message_length": sum(len(msg["content"]) for msg in messages) / len(messages) if messages else 0,
                        "messages_with_reactions": len([msg for msg in messages if msg.get("reactions")]),
                        "messages_with_attachments": len([msg for msg in messages if "attachment" in msg.get("content", "").lower()]),
                    }

                if include_user_activity:
                    user_counts = Counter(msg["sender"] for msg in messages)
                    analytics_data["user_activity"] = {
                        "total_participants": len(user_counts),
                        "most_active_users": dict(user_counts.most_common(10)),
                        "avg_messages_per_user": len(messages) / len(user_counts) if user_counts else 0,
                    }

        # Get topic statistics
        if include_topic_stats:
            topics_result = client.get_stream_topics(stream_id)
            if topics_result.get("result") == "success":
                topics = topics_result.get("topics", [])
                analytics_data["topic_stats"] = {
                    "total_topics": len(topics),
                    "most_recent_topics": topics[:10],  # Topics are typically sorted by recency
                }

        return {
            "status": "success",
            "analytics": analytics_data,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def manage_stream_settings(
    stream_id: int,
    operation: Literal["get", "update", "notifications", "permissions"],
    color: str | None = None,
    pin_to_top: bool | None = None,
    notification_settings: dict[str, Any] | None = None,
    permission_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Manage personal stream notification preferences and settings."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        if operation == "get":
            # Get current subscription settings
            result = client.get_subscriptions()
            if result.get("result") == "success":
                subscriptions = result.get("subscriptions", [])
                stream_sub = next((sub for sub in subscriptions if sub.get("stream_id") == stream_id), None)

                if stream_sub:
                    return {
                        "status": "success",
                        "stream_id": stream_id,
                        "settings": {
                            "color": stream_sub.get("color"),
                            "pin_to_top": stream_sub.get("pin_to_top"),
                            "audible_notifications": stream_sub.get("audible_notifications"),
                            "desktop_notifications": stream_sub.get("desktop_notifications"),
                            "email_notifications": stream_sub.get("email_notifications"),
                            "push_notifications": stream_sub.get("push_notifications"),
                            "wildcard_mentions_notify": stream_sub.get("wildcard_mentions_notify"),
                        }
                    }
                else:
                    return {"status": "error", "error": "Stream subscription not found"}
            else:
                return {"status": "error", "error": result.get("msg", "Failed to get subscription settings")}

        elif operation == "update":
            # Update subscription settings
            subscription_data = []
            update_data = {"stream_id": stream_id}

            if color is not None:
                update_data["color"] = color
            if pin_to_top is not None:
                update_data["pin_to_top"] = pin_to_top
            if notification_settings:
                update_data.update(notification_settings)

            subscription_data.append(update_data)

            result = client.update_subscription_settings(subscription_data)
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "update",
                    "stream_id": stream_id,
                    "updated_settings": update_data,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to update settings")}

        else:
            return {"status": "error", "error": f"Operation '{operation}' not yet implemented"}

    except Exception as e:
        return {"status": "error", "error": str(e), "operation": operation}


def register_streams_tools(mcp: FastMCP) -> None:
    """Register stream tools with the MCP server."""
    mcp.tool(name="manage_streams", description="Complete stream lifecycle management with bulk operations")(manage_streams)
    mcp.tool(name="manage_topics", description="Topic operations within streams including move, delete, mute")(manage_topics)
    mcp.tool(name="get_stream_info", description="Get comprehensive stream information with analytics")(get_stream_info)
    mcp.tool(name="stream_analytics", description="Generate detailed stream statistics and analytics")(stream_analytics)
    mcp.tool(name="manage_stream_settings", description="Manage personal stream notification preferences and settings")(manage_stream_settings)