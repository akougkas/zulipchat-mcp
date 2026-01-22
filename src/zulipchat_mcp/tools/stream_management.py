"""Stream reader tools for ZulipChat MCP v0.4.0.

READ-ONLY stream operations to protect organization from AI changes.
Simple stream discovery and information retrieval only.
"""

from typing import Any

from fastmcp import FastMCP

from ..config import get_config_manager
from ..core.client import ZulipClientWrapper


async def get_streams(
    include_subscribed: bool = True,
    include_public: bool = True,
) -> dict[str, Any]:
    """Get list of streams (READ-ONLY)."""
    config = get_config_manager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_streams(include_subscribed=include_subscribed)
        if result.get("result") == "success":
            streams = result.get("streams", [])

            # Apply filters
            if not include_public:
                streams = [s for s in streams if s.get("invite_only", False)]

            return {
                "status": "success",
                "streams": streams,
                "count": len(streams),
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to list streams"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_stream_info(
    stream_name: str | None = None,
    stream_id: int | None = None,
    include_subscribers: bool = False,
    include_topics: bool = False,
) -> dict[str, Any]:
    """Get detailed information about a specific stream (READ-ONLY)."""
    if not stream_name and not stream_id:
        return {
            "status": "error",
            "error": "Either stream_name or stream_id is required",
        }

    config = get_config_manager()
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
            stream_info = next(
                (s for s in streams if s.get("stream_id") == stream_id), None
            )
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
    """Register READ-ONLY stream tools with the MCP server."""
    mcp.tool(
        name="get_streams", description="Get list of streams (READ-ONLY protection)"
    )(get_streams)
    mcp.tool(
        name="get_stream_info",
        description="Get detailed stream information (READ-ONLY protection)",
    )(get_stream_info)
