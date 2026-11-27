"""Topic management tools for ZulipChat MCP v0.4.0.

Identity-protected topic operations:
- READ-ONLY for user identity (protects organization)
- Full operations for bot identity in Agents-Channel only
- Destructive operations (delete) require --unsafe mode
"""

import asyncio
import difflib
from typing import Annotated, Any, Literal

from pydantic import Field

from ..config import get_client
from ..core.client import ZulipClientWrapper
from ..core.errors import api_error, internal_error, tool_error
from .params import MessageId, Name, page_size

RESOLVED_PREFIX = "✔ "
VISIBILITY_POLICIES = {"inherit": 0, "muted": 1, "unmuted": 2, "followed": 3}


ChannelRef = Annotated[Name | int, Field(description="Channel name or channel ID.")]
TopicName = Annotated[
    str, Field(min_length=1, max_length=60, description="Topic name.")
]


async def get_stream_topics(
    stream_id: Annotated[
        int | None, Field(gt=0, description="Channel ID; used before stream_name.")
    ] = None,
    max_results: Annotated[int, page_size(1000, "topics, most recent first")] = 100,
    stream_name: Annotated[
        str | None, Field(max_length=200, description="Channel name.")
    ] = None,
) -> dict[str, Any]:
    """Get recent topics for a stream by ID or name (READ-ONLY)."""
    if stream_id is None and not stream_name:
        return tool_error("Either stream_id or stream_name is required")
    client = get_client()

    try:
        if stream_id is None:
            name = str(stream_name)
            id_result = await asyncio.to_thread(client.get_stream_id, name)
            if id_result.get("result") != "success":
                return api_error(id_result, f"Stream '{name}' not found")
            stream_id = int(id_result["stream_id"])
        result = await asyncio.to_thread(client.get_stream_topics, stream_id)
        if result.get("result") == "success":
            topics = result.get("topics", [])
            return {
                "status": "success",
                "stream_id": stream_id,
                "topics": topics[:max_results],
                "count": min(len(topics), max_results),
                "total_topics": len(topics),
                "truncated": len(topics) > max_results,
            }
        else:
            return api_error(result, "Failed to list topics")

    except Exception as e:
        return internal_error(e)


async def _stream_id(client: ZulipClientWrapper, stream: str | int) -> int:
    if isinstance(stream, int):
        return stream
    result = await asyncio.to_thread(client.get_stream_id, stream)
    if result.get("result") != "success":
        raise LookupError(result.get("msg") or f"Stream '{stream}' not found")
    return int(result["stream_id"])


async def _latest_message_id(
    client: ZulipClientWrapper, stream_id: int, topic: str
) -> int | None:
    result = await asyncio.to_thread(
        client.get_messages_raw,
        narrow=[
            {"operator": "channel", "operand": stream_id},
            {"operator": "topic", "operand": topic},
        ],
        num_before=1,
        apply_markdown=False,
        use_cache=False,
    )
    if result.get("result") != "success":
        raise RuntimeError(result.get("msg") or "Failed to read topic")
    messages = result.get("messages", [])
    return int(messages[-1]["id"]) if messages else None


async def resolve_topic(
    stream: ChannelRef,
    topic: TopicName,
    resolved: Annotated[
        bool, Field(description="True adds the ✔ prefix; False removes it.")
    ] = True,
) -> dict[str, Any]:
    """Mark a topic resolved ("✔ " prefix) or unresolved; idempotent."""
    client = get_client()
    base = topic.removeprefix(RESOLVED_PREFIX)
    resolved_name = RESOLVED_PREFIX + base
    source, target = (base, resolved_name) if resolved else (resolved_name, base)
    try:
        stream_id = await _stream_id(client, stream)
        message_id = await _latest_message_id(client, stream_id, source)
        if message_id is None:
            if await _latest_message_id(client, stream_id, target) is not None:
                return {"status": "success", "topic": target, "changed": False}
            return tool_error(
                f"Topic '{base}' not found",
                "NOT_FOUND",
                recovery_tool="get_stream_topics",
                hint="List the channel's topics to find the exact name.",
            )
        result = await asyncio.to_thread(
            client.edit_message,
            message_id=message_id,
            topic=target,
            propagate_mode="change_all",
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to rename topic")
        return {"status": "success", "topic": target, "changed": True}
    except LookupError as e:
        return tool_error(str(e), "NOT_FOUND", recovery_tool="get_streams")
    except Exception as e:
        return internal_error(e)


async def set_topic_visibility(
    stream: ChannelRef,
    topic: TopicName,
    policy: Annotated[
        Literal["inherit", "muted", "unmuted", "followed"],
        Field(
            description="followed notifies you of every message; muted hides the "
            "topic; unmuted shows it in a muted channel; inherit uses the "
            "channel's setting."
        ),
    ],
) -> dict[str, Any]:
    """Set the current user's visibility policy for one topic."""
    client = get_client()
    try:
        stream_id = await _stream_id(client, stream)
        result = await asyncio.to_thread(
            client.set_topic_visibility, stream_id, topic, VISIBILITY_POLICIES[policy]
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to set topic visibility")
        return {
            "status": "success",
            "stream_id": stream_id,
            "topic": topic,
            "policy": policy,
        }
    except LookupError as e:
        return tool_error(str(e), "NOT_FOUND", recovery_tool="get_streams")
    except Exception as e:
        return internal_error(e)


def _content_diff(before: str, after: str) -> str:
    lines = difflib.unified_diff(
        before.splitlines(), after.splitlines(), lineterm="", n=0
    )
    return "\n".join(
        line for line in lines if not line.startswith(("---", "+++", "@@"))
    )


async def get_message_history(message_id: MessageId) -> dict[str, Any]:
    """Edit history of a message: who changed what, oldest first."""
    client = get_client()
    try:
        result = await asyncio.to_thread(
            client.client.call_endpoint,
            f"messages/{message_id}/history",
            method="GET",
            request={},
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to get message history")
        users = await asyncio.to_thread(client.get_users)
        names = {u.get("user_id"): u.get("full_name") for u in users.get("members", [])}
        edits: list[dict[str, Any]] = []
        for entry in result.get("message_history", []):
            edit: dict[str, Any] = {
                "timestamp": entry.get("timestamp"),
                "user_id": entry.get("user_id"),
                "user": names.get(entry.get("user_id")),
            }
            if "prev_topic" in entry:
                edit["topic"] = [entry["prev_topic"], entry.get("topic")]
            if "prev_stream" in entry:
                edit["stream"] = [entry["prev_stream"], entry.get("stream")]
            if "prev_content" in entry:
                edit["diff"] = _content_diff(
                    entry["prev_content"], entry.get("content", "")
                )
            elif not edits:
                edit["content"] = entry.get("content")
                edit["topic"] = entry.get("topic")
            edits.append(edit)
        return {
            "status": "success",
            "message_id": message_id,
            "history": edits,
            "edit_count": max(len(edits) - 1, 0),
        }
    except Exception as e:
        return internal_error(e)
