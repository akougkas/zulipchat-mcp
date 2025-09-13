"""Gemini CLI integration capabilities (placeholder).

This is a skeleton implementation that will be enhanced later.
"""

from typing import Any

# Placeholder capabilities
CAPABILITIES: dict[str, dict[str, Any]] = {
    "placeholder": {
        "enabled": False,
        "description": "Placeholder capability for future implementation",
    }
}

DEFAULT_CONFIG: dict[str, Any] = {"agent_type": "gemini-cli", "implemented": False}


def get_capabilities() -> dict[str, Any]:
    """Get capabilities for Gemini CLI integration."""
    return CAPABILITIES


def get_default_config() -> dict[str, Any]:
    """Get default configuration for Gemini CLI integration."""
    return DEFAULT_CONFIG


def get_workflow_commands() -> list[str]:
    """Get workflow commands for Gemini CLI integration."""
    return []


def is_capability_enabled(capability: str) -> bool:
    """Check if capability is enabled."""
    enabled = CAPABILITIES.get(capability, {}).get("enabled", False)
    return bool(enabled)
