"""Topic management tools for ZulipChat MCP v0.4.0.

Identity-protected topic operations:
- READ-ONLY for user identity (protects organization)
- Full operations for bot identity in Agents-Channel only
- Destructive operations (delete) require --unsafe mode
"""

from typing import Any, Literal

from fastmcp import FastMCP

from ..config import get_config_manager
from ..core.client import ZulipClientWrapper
from ..core.security import is_unsafe_mode


async def get_stream_topics(stream_id: int, max_results: int = 100) -> dict[str, Any]:
    """Get recent topics for a stream (READ-ONLY)."""
    config = get_config_manager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_stream_topics(stream_id)
        if result.get("result") == "success":
            topics = result.get("topics", [])
            return {
                "status": "success",
                "stream_id": stream_id,
                "topics": topics[:max_results],
                "count": len(topics),
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to list topics"),
            }

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

    client = ZulipClientWrapper(config, use_bot_identity=True)

    try:
        # Get Agents-Channel stream ID
        stream_result = client.get_stream_id("Agents-Channel")
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
                {"operator": "stream", "operand": str(agents_channel_id)},
                {"operator": "topic", "operand": source_topic},
            ]

            search_result = client.get_messages_raw(
                narrow=narrow, num_before=1, num_after=0
            )

            if search_result.get("result") != "success" or not search_result.get(
                "messages"
            ):
                return {"status": "error", "error": "No messages found in source topic"}

            # Use the existing bot client directly to preserve identity
            # (Do NOT import edit_message wrapper - it creates new user client)
            message_id = search_result["messages"][0]["id"]

            edit_result = client.edit_message(
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

            result = client.delete_topic(agents_channel_id, source_topic)
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "delete",
                    "stream": "Agents-Channel",
                    "topic": source_topic,
                    "protection": "Limited to Agents-Channel only",
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to delete topic"),
                }

        elif operation == "mute":
            result = client.mute_topic(agents_channel_id, source_topic)
            return (
                {
                    "status": "success",
                    "operation": "mute",
                    "stream": "Agents-Channel",
                    "topic": source_topic,
                }
                if result.get("result") == "success"
                else {"status": "error", "error": result.get("msg", "Failed to mute")}
            )

        elif operation == "unmute":
            result = client.unmute_topic(agents_channel_id, source_topic)
            return (
                {
                    "status": "success",
                    "operation": "unmute",
                    "stream": "Agents-Channel",
                    "topic": source_topic,
                }
                if result.get("result") == "success"
                else {"status": "error", "error": result.get("msg", "Failed to unmute")}
            )

        else:
            return {"status": "error", "error": f"Unknown operation: {operation}"}

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
