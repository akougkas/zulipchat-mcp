"""Security module for ZulipChat MCP Server.

Includes:
- Safety mode context (--unsafe flag management)
- Rate limiting
- Input sanitization
- Validation helpers
"""

import os
import re
from contextvars import ContextVar
from pathlib import Path

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


_file_root: Path | None = None


class PathOutsideRoot(ValueError):
    """A local path that resolves outside the configured file root."""


def set_file_root(path: str | os.PathLike[str] | None) -> None:
    """Fix the directory local file paths must stay inside (None: env or cwd)."""
    global _file_root
    _file_root = Path(os.path.realpath(os.path.expanduser(path))) if path else None


def file_root() -> Path:
    """The directory upload_file and download_file may touch."""
    if _file_root is not None:
        return _file_root
    configured = os.getenv("ZULIPCHAT_FILE_ROOT")
    return Path(os.path.realpath(os.path.expanduser(configured or os.getcwd())))


def contained_path(path: str) -> Path:
    """Resolve path (relative to the working directory, symlinks followed).

    Raises PathOutsideRoot unless the result is the file root or inside it.
    """
    root = file_root()
    resolved = Path(os.path.realpath(os.path.expanduser(path)))
    if resolved != root and root not in resolved.parents:
        raise PathOutsideRoot(f"{path} resolves outside the file root {root}")
    return resolved


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
