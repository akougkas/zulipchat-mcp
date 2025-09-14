"""Stream management tools for ZulipChat MCP v2.5.1.

Core stream operations: list, create, subscribe, unsubscribe, delete.
Direct mapping to Zulip's stream API endpoints.
"""

from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


async def get_streams(
    include_public: bool = True,
    include_subscribed: bool = True,
    include_all_active: bool = False,
    include_web_public: bool = False,
    include_owner_subscribed: bool = False,
) -> dict[str, Any]:
    """Get list of streams with filtering options."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
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

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def create_streams(
    stream_names: list[str],
    descriptions: list[str] | None = None,
    invite_only: bool = False,
    principals: list[str] | None = None,
    announce: bool = False,
    history_public_to_subscribers: bool | None = None,
    stream_post_policy: int | None = None,
    message_retention_days: int | None = None,
) -> dict[str, Any]:
    """Create one or more streams."""
    if not stream_names:
        return {"status": "error", "error": "Stream names required"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Build streams to create
        streams_to_create = []
        for i, name in enumerate(stream_names):
            stream_def = {"name": name}
            if descriptions and i < len(descriptions):
                stream_def["description"] = descriptions[i]
            if invite_only:
                stream_def["invite_only"] = True
            streams_to_create.append(stream_def)

        result = client.add_subscriptions(
            subscriptions=streams_to_create,
            principals=principals,
            announce=announce,
            authorization_errors_fatal=True,
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "created": result.get("subscribed", {}),
                "already_existed": result.get("already_subscribed", {}),
                "stream_count": len(stream_names),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to create streams")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def subscribe_to_streams(
    stream_names: list[str],
    principals: list[str] | None = None,
    announce: bool = False,
) -> dict[str, Any]:
    """Subscribe to existing streams."""
    if not stream_names:
        return {"status": "error", "error": "Stream names required"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        streams_to_sub = [{"name": name} for name in stream_names]
        result = client.add_subscriptions(
            subscriptions=streams_to_sub,
            principals=principals,
            announce=announce,
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "subscribed": result.get("subscribed", {}),
                "already_subscribed": result.get("already_subscribed", {}),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to subscribe")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def unsubscribe_from_streams(stream_names: list[str]) -> dict[str, Any]:
    """Unsubscribe from streams."""
    if not stream_names:
        return {"status": "error", "error": "Stream names required"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.remove_subscriptions(stream_names)

        if result.get("result") == "success":
            return {
                "status": "success",
                "unsubscribed": result.get("removed", []),
                "not_removed": result.get("not_removed", []),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to unsubscribe")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def delete_streams(stream_ids: list[int]) -> dict[str, Any]:
    """Delete streams by ID."""
    if not stream_ids:
        return {"status": "error", "error": "Stream IDs required"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
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
            "deleted": deleted,
            "errors": errors,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_stream_info(
    stream_name: str | None = None,
    stream_id: int | None = None,
    include_subscribers: bool = False,
    include_topics: bool = False,
) -> dict[str, Any]:
    """Get detailed information about a specific stream."""
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

        # Get basic stream information
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
            "is_web_public": stream_info.get("is_web_public", False),
            "stream_post_policy": stream_info.get("stream_post_policy"),
            "message_retention_days": stream_info.get("message_retention_days"),
            "history_public_to_subscribers": stream_info.get("history_public_to_subscribers"),
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
                info["topics"] = topics_result.get("topics", [])
                info["topic_count"] = len(topics_result.get("topics", []))

        return info

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_stream_management_tools(mcp: FastMCP) -> None:
    """Register stream management tools with the MCP server."""
    mcp.tool(name="get_streams", description="Get list of streams with filtering options")(get_streams)
    mcp.tool(name="create_streams", description="Create one or more streams")(create_streams)
    mcp.tool(name="subscribe_to_streams", description="Subscribe to existing streams")(subscribe_to_streams)
    mcp.tool(name="unsubscribe_from_streams", description="Unsubscribe from streams")(unsubscribe_from_streams)
    mcp.tool(name="delete_streams", description="Delete streams by ID")(delete_streams)
    mcp.tool(name="get_stream_info", description="Get detailed information about a specific stream")(get_stream_info)