"""Emoji reaction tools for ZulipChat MCP v2.5.1.

Clean implementation of Zulip's emoji reaction API endpoints.
Direct mapping to add/remove reaction APIs.
"""

import re
from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


def validate_emoji(emoji_name: str) -> bool:
    """Validate emoji name against injection."""
    pattern = r"^[a-zA-Z0-9_]+$"
    return bool(re.match(pattern, emoji_name)) and 0 < len(emoji_name) <= 50


async def add_reaction(
    message_id: int,
    emoji_name: str,
    emoji_code: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Add emoji reaction to message with validation."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {
            "status": "error",
            "error": {
                "code": "INVALID_MESSAGE_ID",
                "message": "Invalid message ID. Must be a positive integer.",
                "suggestions": ["Use search_messages to find valid message IDs"]
            }
        }

    if not validate_emoji(emoji_name):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_EMOJI_NAME",
                "message": f"Invalid emoji name: '{emoji_name}'",
                "suggestions": [
                    "Use alphanumeric characters and underscores only",
                    "Keep emoji name under 50 characters",
                    "Check available emojis in your Zulip organization"
                ]
            }
        }

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Prepare request data for Zulip API
        request_data = {
            "message_id": message_id,
            "emoji_name": emoji_name,
            "reaction_type": reaction_type,
        }

        if emoji_code:
            request_data["emoji_code"] = emoji_code

        result = client.add_reaction(message_id, emoji_name)

        if result.get("result") == "success":
            return {
                "status": "success",
                "message_id": message_id,
                "emoji_name": emoji_name,
                "emoji_code": emoji_code,
                "reaction_type": reaction_type,
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to add reaction")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def remove_reaction(
    message_id: int,
    emoji_name: str,
    emoji_code: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Remove emoji reaction from message with validation."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {"status": "error", "error": "Invalid message ID"}

    if not validate_emoji(emoji_name):
        return {"status": "error", "error": f"Invalid emoji name: '{emoji_name}'"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.remove_reaction(message_id, emoji_name)

        if result.get("result") == "success":
            return {
                "status": "success",
                "message_id": message_id,
                "emoji_name": emoji_name,
                "emoji_code": emoji_code,
                "reaction_type": reaction_type,
                "action": "removed",
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to remove reaction")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_emoji_messaging_tools(mcp: FastMCP) -> None:
    """Register emoji reaction tools with the MCP server."""
    mcp.tool(name="add_reaction", description="Add emoji reaction to message with comprehensive validation")(add_reaction)
    mcp.tool(name="remove_reaction", description="Remove emoji reaction from message")(remove_reaction)