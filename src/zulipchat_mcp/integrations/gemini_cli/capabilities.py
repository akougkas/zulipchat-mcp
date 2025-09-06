"""Gemini CLI integration capabilities (placeholder).

This is a skeleton implementation that will be enhanced later.
"""

from typing import Any

# Placeholder capabilities
CAPABILITIES = {
    "placeholder": {
        "enabled": False,
        "description": "Placeholder capability for future implementation",
    }
}

DEFAULT_CONFIG = {"agent_type": "gemini-cli", "implemented": False}


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
    return CAPABILITIES.get(capability, {}).get("enabled", False)
