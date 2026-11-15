"""Topic management tools for ZulipChat MCP v0.4.0.

Identity-protected topic operations:
- READ-ONLY for user identity (protects organization)
- Full operations for bot identity in Agents-Channel only
- Destructive operations (delete) require --unsafe mode
"""

import asyncio
import difflib
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import get_bot_client, get_client, get_config_manager
from ..core.api_errors import api_error
from ..core.client import ZulipClientWrapper
from ..core.security import is_unsafe_mode

RESOLVED_PREFIX = "✔ "
VISIBILITY_POLICIES = {"inherit": 0, "muted": 1, "unmuted": 2, "followed": 3}


async def get_stream_topics(
    stream_id: int | None = None,
    max_results: int = 100,
    stream_name: str | None = None,
) -> dict[str, Any]:
    """Get recent topics for a stream by ID or name (READ-ONLY)."""
    if stream_id is None and not stream_name:
        return {
            "status": "error",
            "error": "Either stream_id or stream_name is required",
        }
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
                "count": len(topics),
            }
        else:
            return api_error(result, "Failed to list topics")

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def agents_channel_topic_ops(
    operation: Literal["move", "delete", "mute", "unmute"],
    source_topic: str,
    target_topic: str | None = None,
    propagate_mode: Literal["change_one", "change_later", "change_all"] = "change_all",
) -> dict[str, Any]:
    """Topic operations in Agents-Channel only (BOT identity protection)."""
    config = get_config_manager()

    # Force bot identity for organizational protection
    if not config.has_bot_credentials():
        return {
            "status": "error",
            "error": "Bot credentials required for topic operations",
            "protection": "Prevents AI from modifying organization streams",
        }

    client = get_bot_client()  # Always use bot identity for this operation

    try:
        # Get Agents-Channel stream ID
        stream_result = await asyncio.to_thread(client.get_stream_id, "Agents-Channel")
        if stream_result.get("result") != "success":
            return {"status": "error", "error": "Agents-Channel not found"}

        agents_channel_id = stream_result.get("stream_id")
        if not isinstance(agents_channel_id, int):
            return {
                "status": "error",
                "error": "Agents-Channel stream_id unavailable",
            }

        if operation == "move":
            if not target_topic:
                return {
                    "status": "error",
                    "error": "target_topic required for move operation",
                }

            # Find message in source topic
            narrow = [
                {"operator": "channel", "operand": str(agents_channel_id)},
                {"operator": "topic", "operand": source_topic},
            ]

            search_result = await asyncio.to_thread(
                client.get_messages_raw, narrow=narrow, num_before=1, num_after=0
            )

            if search_result.get("result") != "success" or not search_result.get(
                "messages"
            ):
                return {"status": "error", "error": "No messages found in source topic"}

            # Use the existing bot client directly to preserve identity
            # (Do NOT import edit_message wrapper - it creates new user client)
            message_id = search_result["messages"][0]["id"]

            edit_result = await asyncio.to_thread(
                client.edit_message,
                message_id=message_id,
                topic=target_topic,
                propagate_mode=propagate_mode,
            )

            if edit_result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "move",
                    "stream": "Agents-Channel",
                    "source_topic": source_topic,
                    "target_topic": target_topic,
                    "protection": "Limited to Agents-Channel only",
                }
            else:
                return {
                    "status": "error",
                    "error": edit_result.get("error", "Failed to move topic"),
                }

        elif operation == "delete":
            # Delete requires --unsafe mode
            if not is_unsafe_mode():
                return {
                    "status": "error",
                    "error": "Delete operation requires --unsafe mode",
                    "hint": "Start the server with --unsafe flag to enable destructive operations",
                }

            result = await asyncio.to_thread(
                client.delete_topic, agents_channel_id, source_topic
            )
            if result.get("result") != "success":
                return api_error(result, "Failed to delete topic")
            outcome = {
                "operation": "delete",
                "stream": "Agents-Channel",
                "topic": source_topic,
                "complete": result.get("complete", True),
                "batches": result.get("batches", 1),
            }
            if not outcome["complete"]:
                return {
                    "status": "error",
                    "error": "Topic only partially deleted; run delete again",
                    "retryable": True,
                    **outcome,
                }
            return {"status": "success", **outcome}

        elif operation in ("mute", "unmute"):
            result = await asyncio.to_thread(
                client.set_topic_visibility,
                agents_channel_id,
                source_topic,
                1 if operation == "mute" else 0,
            )
            if result.get("result") != "success":
                return api_error(result, f"Failed to {operation}")
            return {
                "status": "success",
                "operation": operation,
                "stream": "Agents-Channel",
                "topic": source_topic,
            }

        else:
            return {"status": "error", "error": f"Unknown operation: {operation}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


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
    stream: str | int, topic: str, resolved: bool = True
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
            return {"status": "error", "error": f"Topic '{base}' not found"}
        result = await asyncio.to_thread(
            client.edit_message,
            message_id=message_id,
            topic=target,
            propagate_mode="change_all",
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to rename topic")
        return {"status": "success", "topic": target, "changed": True}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def set_topic_visibility(
    stream: str | int,
    topic: str,
    policy: Literal["inherit", "muted", "unmuted", "followed"],
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
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _content_diff(before: str, after: str) -> str:
    lines = difflib.unified_diff(
        before.splitlines(), after.splitlines(), lineterm="", n=0
    )
    return "\n".join(
        line for line in lines if not line.startswith(("---", "+++", "@@"))
    )


async def get_message_history(message_id: int) -> dict[str, Any]:
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
        return {"status": "error", "error": str(e)}


def register_topic_management_tools(mcp: FastMCP) -> None:
    """Register topic management tools with identity protection."""
    mcp.tool(
        name="get_stream_topics",
        description="Get recent topics for a stream (READ-ONLY)",
    )(get_stream_topics)
    mcp.tool(
        name="agents_channel_topic_ops",
        description="Topic operations in Agents-Channel only (BOT identity protection)",
    )(agents_channel_topic_ops)
