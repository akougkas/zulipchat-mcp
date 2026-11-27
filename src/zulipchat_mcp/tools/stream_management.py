"""Stream reader tools for ZulipChat MCP v0.4.0.

READ-ONLY stream operations to protect organization from AI changes.
Simple stream discovery and information retrieval only.
"""

import asyncio
from typing import Annotated, Any

from pydantic import Field

from ..config import get_client
from ..core.errors import api_error, internal_error, tool_error

# Raw Zulip stream objects carry ~30 permission/group fields each; a realm with
# a few dozen streams then exceeds typical MCP client result budgets.
STREAM_SUMMARY_FIELDS = (
    "stream_id",
    "name",
    "description",
    "invite_only",
    "is_web_public",
    "is_archived",
)


async def get_streams(
    include_subscribed: Annotated[
        bool, Field(description="Include channels you are subscribed to.")
    ] = True,
    include_public: Annotated[
        bool, Field(description="Include public channels you are not in.")
    ] = True,
    verbose: Annotated[
        bool,
        Field(
            description="Return Zulip's full channel objects instead of ID, name, "
            "description and visibility."
        ),
    ] = False,
) -> dict[str, Any]:
    """Get list of streams (READ-ONLY). Set verbose for raw Zulip objects."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            client.get_streams,
            include_subscribed=include_subscribed,
            include_public=include_public,
        )
        if result.get("result") == "success":
            streams = result.get("streams", [])
            if not verbose:
                streams = [
                    {key: stream[key] for key in STREAM_SUMMARY_FIELDS if key in stream}
                    for stream in streams
                ]

            return {
                "status": "success",
                "streams": streams,
                "count": len(streams),
            }
        else:
            return api_error(result, "Failed to list streams")

    except Exception as e:
        return internal_error(e)


async def get_stream_info(
    stream_name: Annotated[
        str | None, Field(max_length=200, description="Channel name.")
    ] = None,
    stream_id: Annotated[
        int | None, Field(gt=0, description="Channel ID; used before stream_name.")
    ] = None,
    include_subscribers: Annotated[
        bool, Field(description="Add the subscriber user IDs.")
    ] = False,
    include_topics: Annotated[
        bool, Field(description="Add the channel's recent topics.")
    ] = False,
) -> dict[str, Any]:
    """Get detailed information about a specific stream (READ-ONLY)."""
    if not stream_name and not stream_id:
        return tool_error("Either stream_name or stream_id is required")

    client = get_client()

    try:
        if not stream_id:
            id_result = await asyncio.to_thread(client.get_stream_id, str(stream_name))
            if id_result.get("result") != "success":
                return api_error(id_result, f"Stream '{stream_name}' not found")
            stream_id = int(id_result["stream_id"])

        stream_result = await asyncio.to_thread(client.get_stream, stream_id)
        if stream_result.get("result") != "success":
            return api_error(stream_result, "Failed to get stream information")
        stream_info = stream_result.get("stream", {})

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
            sub_result = await asyncio.to_thread(client.get_subscribers, stream_id)
            if sub_result.get("result") == "success":
                info["subscribers"] = sub_result.get("subscribers", [])
                info["subscriber_count"] = len(sub_result.get("subscribers", []))
            else:
                info["status"] = "partial"
                info["error"] = api_error(sub_result, "Subscribers unavailable")[
                    "error"
                ]
                info.setdefault("errors", []).append(
                    {"component": "subscribers", **info["error"]}
                )

        # Get topics if requested
        if include_topics and stream_id:
            topics_result = await asyncio.to_thread(client.get_stream_topics, stream_id)
            if topics_result.get("result") == "success":
                info["topics"] = topics_result.get("topics", [])
                info["topic_count"] = len(topics_result.get("topics", []))
            else:
                info["status"] = "partial"
                info["error"] = api_error(topics_result, "Topics unavailable")["error"]
                info.setdefault("errors", []).append(
                    {"component": "topics", **info["error"]}
                )

        return info

    except Exception as e:
        return internal_error(e)
