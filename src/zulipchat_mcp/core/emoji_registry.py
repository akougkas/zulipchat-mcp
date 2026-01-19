"""Approved emoji registry for agent reactions."""

from typing import Any

APPROVED_EMOJI = {
    "thumbs_up": "Approval or agreement",
    "heart": "Support, love, or encouragement",
    "rocket": "Launch, deployment, or success",
    "fire": "Hot topic, importance, or urgency",
    "tada": "Celebration or achievement",
    "check_mark": "Completion or verification",
    "warning": "Alert, caution, or issue",
    "thinking": "Analysis, consideration, or review",
    "bulb": "Idea, insight, or discovery",
    "wrench": "Fix, tool, or implementation",
    "star": "Quality, favorite, or highlight",
    "zap": "Energy, quick action, or breakthrough",
}


def validate_emoji_for_agent(emoji_name: str) -> tuple[bool, str]:
    """Validate emoji for agent use.

    Args:
        emoji_name: Name of emoji to validate

    Returns:
        Tuple of (is_valid, description_or_error)
    """
    if emoji_name in APPROVED_EMOJI:
        return True, APPROVED_EMOJI[emoji_name]

    approved_list = ", ".join(list(APPROVED_EMOJI.keys())[:5]) + "..."
    return False, f"Emoji '{emoji_name}' not approved. Use: {approved_list}"


def get_emoji_choices() -> list[dict[str, str]]:
    """Return approved emoji choices for agents.

    Returns:
        List of dicts with 'name' and 'description' keys
    """
    return [
        {"name": name, "description": desc}
        for name, desc in APPROVED_EMOJI.items()
    ]
