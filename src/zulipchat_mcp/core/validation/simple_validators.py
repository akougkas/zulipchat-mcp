"""Simplified parameter validation following 'simple by default, powerful when needed' principle.

This module provides streamlined validation that supports progressive disclosure
without the complexity of over-engineered validation systems.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


class ValidationMode(Enum):
    """Validation modes for progressive disclosure."""

    BASIC = "basic"      # Essential parameters only
    ADVANCED = "advanced"  # All parameters available
    EXPERT = "expert"    # Expert mode with minimal validation


class SimpleValidator:
    """Simplified validator that follows progressive disclosure principles."""

    # Essential parameters for basic mode
    BASIC_PARAMS = {
        "messaging.message": {"operation", "type", "to", "content"},
        "messaging.search_messages": {"narrow", "num_before"},
        "messaging.edit_message": {"message_id"},
        "streams.manage_streams": {"operation"},
        "events.register_events": {"event_types"},
        "users.manage_users": {"operation"},
        "search.advanced_search": {"query"},
        "files.upload_file": {"filename"},
        "admin.admin_operations": {"operation"},
    }

    # Required parameters that must always be present
    REQUIRED_PARAMS = {
        "messaging.message": {"operation", "type", "to", "content"},
        "messaging.search_messages": set(),  # All optional with defaults
        "messaging.edit_message": {"message_id"},
        "streams.manage_streams": {"operation"},
        "events.register_events": {"event_types"},
        "users.manage_users": {"operation"},
        "search.advanced_search": {"query"},
        "files.upload_file": {"filename"},
        "admin.admin_operations": {"operation"},
    }

    def validate_params(
        self,
        tool: str,
        params: dict[str, Any],
        mode: ValidationMode = ValidationMode.BASIC
    ) -> dict[str, Any]:
        """Validate tool parameters with progressive disclosure.
        
        Args:
            tool: Tool name to validate
            params: Parameters to validate
            mode: Validation mode
            
        Returns:
            Validated and filtered parameters
            
        Raises:
            ValueError: If required parameters are missing
        """
        if mode == ValidationMode.EXPERT:
            # Expert mode: minimal validation, trust the user
            return self._validate_required_only(tool, params)

        if mode == ValidationMode.BASIC:
            # Basic mode: filter to essential parameters only
            allowed_params = self.BASIC_PARAMS.get(tool, set())
            filtered_params = {k: v for k, v in params.items() if k in allowed_params}
            return self._validate_required_only(tool, filtered_params)

        # Advanced mode: full validation
        return self._validate_required_only(tool, params)

    def _validate_required_only(self, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        """Basic validation - just check required parameters.
        
        Args:
            tool: Tool name
            params: Parameters to validate
            
        Returns:
            Validated parameters
            
        Raises:
            ValueError: If required parameters are missing
        """
        required = self.REQUIRED_PARAMS.get(tool, set())
        missing = required - set(params.keys())

        if missing:
            raise ValueError(f"Missing required parameters for {tool}: {missing}")

        return params

    def get_parameter_help(self, tool: str, mode: ValidationMode = ValidationMode.BASIC) -> dict[str, Any]:
        """Get help information for tool parameters.
        
        Args:
            tool: Tool name
            mode: What level of help to provide
            
        Returns:
            Parameter help information
        """
        help_info = {
            "tool": tool,
            "mode": mode.value,
            "required": list(self.REQUIRED_PARAMS.get(tool, set())),
        }

        if mode == ValidationMode.BASIC:
            help_info["basic_params"] = list(self.BASIC_PARAMS.get(tool, set()))
            help_info["message"] = "Basic mode: showing essential parameters only"
        elif mode == ValidationMode.ADVANCED:
            help_info["message"] = "Advanced mode: all parameters available"
        else:
            help_info["message"] = "Expert mode: minimal validation"

        return help_info


class NarrowHelper:
    """Simplified helper for building Zulip narrow filters."""

    @staticmethod
    def stream(name: str) -> dict[str, str]:
        """Create stream filter."""
        return {"operator": "stream", "operand": name}

    @staticmethod
    def topic(name: str) -> dict[str, str]:
        """Create topic filter."""
        return {"operator": "topic", "operand": name}

    @staticmethod
    def sender(email: str) -> dict[str, str]:
        """Create sender filter."""
        return {"operator": "sender", "operand": email}

    @staticmethod
    def search_text(text: str) -> dict[str, str]:
        """Create text search filter."""
        return {"operator": "search", "operand": text}

    @staticmethod
    def has_attachment() -> dict[str, str]:
        """Create attachment filter."""
        return {"operator": "has", "operand": "attachment"}

    @staticmethod
    def is_private() -> dict[str, str]:
        """Create private message filter."""
        return {"operator": "is", "operand": "private"}

    @classmethod
    def build_basic_narrow(
        cls,
        stream: str | None = None,
        topic: str | None = None,
        sender: str | None = None,
        text: str | None = None
    ) -> list[dict[str, str]]:
        """Build a basic narrow filter from common parameters.
        
        Args:
            stream: Stream name
            topic: Topic name
            sender: Sender email
            text: Text to search for
            
        Returns:
            List of narrow filters
        """
        narrow = []

        if stream:
            narrow.append(cls.stream(stream))
        if topic:
            narrow.append(cls.topic(topic))
        if sender:
            narrow.append(cls.sender(sender))
        if text:
            narrow.append(cls.search_text(text))

        return narrow


# Global validator instance
_validator: SimpleValidator | None = None


def get_validator() -> SimpleValidator:
    """Get the global validator instance."""
    global _validator
    if _validator is None:
        _validator = SimpleValidator()
    return _validator


def validate_tool_params(
    tool: str,
    params: dict[str, Any],
    mode: ValidationMode = ValidationMode.BASIC
) -> dict[str, Any]:
    """Convenience function for parameter validation.
    
    Args:
        tool: Tool name
        params: Parameters to validate
        mode: Validation mode
        
    Returns:
        Validated parameters
    """
    return get_validator().validate_params(tool, params, mode)
