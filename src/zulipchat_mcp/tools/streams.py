"""Stream analytics and settings tools for ZulipChat MCP v2.5.1.

Analytics and settings operations for streams.
Core management moved to stream_management.py, topics moved to topic_management.py.
"""

from collections import Counter
from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


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
    operation: Literal["get", "update"],
    color: str | None = None,
    pin_to_top: bool | None = None,
    notification_settings: dict[str, Any] | None = None,
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
                    "stream_id": stream_id,
                    "updated_settings": update_data,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to update settings")}

        else:
            return {"status": "error", "error": f"Operation '{operation}' not implemented"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_streams_tools(mcp: FastMCP) -> None:
    """Register stream analytics and settings tools with the MCP server."""
    mcp.tool(name="stream_analytics", description="Generate detailed stream statistics and analytics")(stream_analytics)
    mcp.tool(name="manage_stream_settings", description="Manage personal stream notification preferences and settings")(manage_stream_settings)