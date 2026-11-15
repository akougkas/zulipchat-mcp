"""Security module for ZulipChat MCP Server.

Includes:
- Safety mode context (--unsafe flag management)
- Rate limiting
- Input sanitization
- Validation helpers
"""

import re
from contextvars import ContextVar

from fastmcp.server.dependencies import get_http_headers, get_http_request

# Global safety mode context - defaults to SAFE (unsafe_mode=False)
_unsafe_mode: ContextVar[bool] = ContextVar("unsafe_mode", default=False)


def local_access_allowed() -> bool:
    """Local paths and identity switching belong to the local stdio trust boundary."""
    # Tasks restore the submitting HTTP headers, but have no live Request.
    if get_http_headers(include_all=True):
        return False
    try:
        get_http_request()
    except RuntimeError:
        return True
    return False


def set_unsafe_mode(enabled: bool) -> None:
    """Set the global safety mode.

    Args:
        enabled: If True, dangerous operations are allowed.
    """
    _unsafe_mode.set(enabled)


def is_unsafe_mode() -> bool:
    """Check if unsafe mode is enabled.

    Returns:
        True if unsafe operations are allowed, False otherwise.
    """
    return _unsafe_mode.get()


def validate_emoji(emoji_name: str) -> bool:
    """Validate emoji name.

    Args:
        emoji_name: Name of the emoji to validate

    Returns:
        True if valid, False otherwise
    """
    # Emoji names are typically alphanumeric with underscores
    pattern = r"^[a-zA-Z0-9_]+$"
    return bool(re.match(pattern, emoji_name)) and 0 < len(emoji_name) <= 50


def validate_email(email: str) -> bool:
    """Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))
