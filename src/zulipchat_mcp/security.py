"""Security module for ZulipChat MCP Server."""

import html
import re
import time
from collections.abc import Callable
from functools import wraps
from typing import Any


class RateLimiter:
    """Rate limiting implementation for API calls."""

    def __init__(self, max_calls: int = 100, window: int = 60) -> None:
        """Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed in the window
            window: Time window in seconds
        """
        self.max_calls = max_calls
        self.window = window
        self.calls: dict[str, list[float]] = {}

    def check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limit.

        Args:
            client_id: Unique identifier for the client

        Returns:
            True if within limits, False otherwise
        """
        now = time.time()
        if client_id not in self.calls:
            self.calls[client_id] = []

        # Clean old calls
        self.calls[client_id] = [
            t for t in self.calls[client_id]
            if now - t < self.window
        ]

        if len(self.calls[client_id]) >= self.max_calls:
            return False

        self.calls[client_id].append(now)
        return True


def sanitize_input(content: str, max_length: int = 10000) -> str:
    """Sanitize user input to prevent injection attacks.

    Args:
        content: The input content to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized content string
    """
    # HTML escape
    content = html.escape(content)

    # Remove potential command injections (conservative approach)
    # Only remove backticks that might be used for command substitution
    content = re.sub(r'`', '', content)

    # Limit length
    return content[:max_length]


def validate_stream_name(name: str) -> bool:
    """Validate stream name against injection.

    Args:
        name: Stream name to validate

    Returns:
        True if valid, False otherwise
    """
    # Allow alphanumeric, spaces, hyphens, underscores, and dots
    pattern = r'^[a-zA-Z0-9\-_\s\.]+$'
    return bool(re.match(pattern, name)) and 0 < len(name) <= 100


def validate_topic(topic: str) -> bool:
    """Validate topic name against injection.

    Args:
        topic: Topic name to validate

    Returns:
        True if valid, False otherwise
    """
    # Topics can have more varied characters but still need validation
    pattern = r'^[a-zA-Z0-9\-_\s\.\,\!\?\(\)]+$'
    return bool(re.match(pattern, topic)) and 0 < len(topic) <= 200


def validate_emoji(emoji_name: str) -> bool:
    """Validate emoji name.

    Args:
        emoji_name: Name of the emoji to validate

    Returns:
        True if valid, False otherwise
    """
    # Emoji names are typically alphanumeric with underscores
    pattern = r'^[a-zA-Z0-9_]+$'
    return bool(re.match(pattern, emoji_name)) and 0 < len(emoji_name) <= 50


def validate_email(email: str) -> bool:
    """Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_message_type(message_type: str) -> bool:
    """Validate message type.

    Args:
        message_type: Type of message (stream or private)

    Returns:
        True if valid, False otherwise
    """
    return message_type in ["stream", "private"]


def rate_limit_decorator(
    max_calls: int = 100,
    window: int = 60
) -> Callable:
    """Decorator for applying rate limiting to functions.

    Args:
        max_calls: Maximum calls allowed in window
        window: Time window in seconds

    Returns:
        Decorated function with rate limiting
    """
    limiter = RateLimiter(max_calls, window)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Try to extract client identifier from context
            # In a real implementation, this would come from the MCP context
            client_id = "default"

            if not limiter.check_rate_limit(client_id):
                return {
                    "status": "error",
                    "error": "Rate limit exceeded. Please try again later."
                }

            return func(*args, **kwargs)
        return wrapper
    return decorator


def secure_log(message: str, sensitive_keys: list[str] | None = None) -> str:
    """Sanitize log messages to remove sensitive information.

    Args:
        message: Log message to sanitize
        sensitive_keys: List of keys to redact

    Returns:
        Sanitized log message
    """
    if sensitive_keys is None:
        sensitive_keys = ["api_key", "password", "token", "secret"]

    sanitized = message
    for key in sensitive_keys:
        # Redact values after these keys
        pattern = rf"({key}['\"]?\s*[:=]\s*['\"]?)([^'\"]+)(['\"]?)"
        sanitized = re.sub(pattern, r'\1[REDACTED]\3', sanitized, flags=re.IGNORECASE)

    return sanitized
