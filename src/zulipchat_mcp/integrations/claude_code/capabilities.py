"""Claude Code integration capabilities.

This module declares optional agent-specific features and toggles for Claude Code
without leaking brand specifics into the core system.
"""

from typing import Any

# Claude Code specific capabilities
CAPABILITIES = {
    "status_line_indicator": {
        "enabled": True,
        "description": "Show Zulip activity in Claude Code status line",
        "config_key": "zulip.statusLine.enabled",
    },
    "afk_aware_notifications": {
        "enabled": True,
        "description": "Only send notifications when user is AFK",
        "config_key": "zulip.notifications.afkAware",
    },
    "auto_register_agent": {
        "enabled": True,
        "description": "Automatically register agent on startup",
        "config_key": "zulip.agent.autoRegister",
    },
    "workflow_commands": {
        "enabled": True,
        "description": "Install workflow command shortcuts",
        "workflows": ["daily_summary", "morning_briefing", "catch_up"],
    },
}

# Default configuration for Claude Code
DEFAULT_CONFIG = {
    "agent_type": "claude-code",
    "default_stream": "Agent-Channel",
    "status_update_interval": 30,
    "max_message_length": 2000,
    "retry_attempts": 3,
}


def get_capabilities() -> dict[str, Any]:
    """Get all capabilities for Claude Code integration.

    Returns:
        Dictionary of capabilities and their configurations
    """
    return CAPABILITIES


def get_default_config() -> dict[str, Any]:
    """Get default configuration for Claude Code integration.

    Returns:
        Dictionary of default configuration values
    """
    return DEFAULT_CONFIG


def get_workflow_commands() -> list[str]:
    """Get list of workflow commands supported by Claude Code.

    Returns:
        List of workflow command names
    """
    if CAPABILITIES["workflow_commands"]["enabled"]:
        return CAPABILITIES["workflow_commands"]["workflows"]
    return []


def is_capability_enabled(capability: str) -> bool:
    """Check if a specific capability is enabled.

    Args:
        capability: Name of the capability to check

    Returns:
        True if capability is enabled, False otherwise
    """
    return CAPABILITIES.get(capability, {}).get("enabled", False)
