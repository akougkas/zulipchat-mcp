"""Emoji reaction tools for ZulipChat MCP v0.4.0.

Clean implementation of Zulip's emoji reaction API endpoints.
Direct mapping to add/remove reaction APIs.
"""

import asyncio
import re
from typing import Annotated, Any, Literal

from pydantic import Field

from ..config import get_client
from ..core.emoji_registry import validate_emoji_for_agent
from ..core.errors import api_error, internal_error, tool_error
from .params import MessageId

EmojiName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Emoji name. Adding accepts only thumbs_up, heart, rocket, "
        "fire, tada, check_mark, warning, thinking, bulb, wrench, star, zap.",
    ),
]
EmojiCode = Annotated[
    str | None,
    Field(max_length=50, description="Emoji code; needed for realm emoji."),
]
ReactionType = Annotated[
    Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"],
    Field(description="Kind of emoji named by emoji_name."),
]


def validate_emoji(emoji_name: str) -> bool:
    """Validate emoji name against injection."""
    pattern = r"^[a-zA-Z0-9_]+$"
    return bool(re.match(pattern, emoji_name)) and 0 < len(emoji_name) <= 50


async def add_reaction(
    message_id: MessageId,
    emoji_name: EmojiName,
    emoji_code: EmojiCode = None,
    reaction_type: ReactionType = "unicode_emoji",
    remove: Annotated[
        bool,
        Field(description="Take back your own reaction instead of adding one."),
    ] = False,
) -> dict[str, Any]:
    """Add an emoji reaction to a message, or take it back with remove=True."""
    if remove:
        return await remove_reaction(message_id, emoji_name, emoji_code, reaction_type)
    if not isinstance(message_id, int) or message_id <= 0:
        return tool_error(
            "Invalid message ID. Must be a positive integer.",
            recovery_tool="search_messages",
            hint="Find a valid message ID with search_messages.",
        )

    is_valid, error_msg = validate_emoji_for_agent(emoji_name)
    if not is_valid:
        return tool_error(
            error_msg, "INVALID_EMOJI_NAME", hint="Use one of the approved emoji."
        )

    client = get_client()

    try:
        # Prepare request data for Zulip API
        request_data: dict[str, str] = {"reaction_type": reaction_type}

        if emoji_code:
            request_data["emoji_code"] = emoji_code

        result = await asyncio.to_thread(
            client.add_reaction, message_id, emoji_name, **request_data
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "message_id": message_id,
                "emoji_name": emoji_name,
                "emoji_code": emoji_code,
                "reaction_type": reaction_type,
            }
        else:
            return api_error(result, "Failed to add reaction")

    except Exception as e:
        return internal_error(e)


async def remove_reaction(
    message_id: int,
    emoji_name: str,
    emoji_code: str | None = None,
    reaction_type: Literal[
        "unicode_emoji", "realm_emoji", "zulip_extra_emoji"
    ] = "unicode_emoji",
) -> dict[str, Any]:
    """Remove emoji reaction from message with validation."""
    if not isinstance(message_id, int) or message_id <= 0:
        return tool_error("Invalid message ID")

    if not validate_emoji(emoji_name):
        return tool_error(f"Invalid emoji name: '{emoji_name}'")

    client = get_client()

    try:
        request_data: dict[str, str] = {"reaction_type": reaction_type}
        if emoji_code:
            request_data["emoji_code"] = emoji_code
        result = await asyncio.to_thread(
            client.remove_reaction, message_id, emoji_name, **request_data
        )

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
            return api_error(result, "Failed to remove reaction")

    except Exception as e:
        return internal_error(e)
