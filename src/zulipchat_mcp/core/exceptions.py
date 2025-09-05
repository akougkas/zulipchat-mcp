"""Custom exceptions for ZulipChat MCP Server."""

from datetime import datetime
from typing import Any


class ZulipMCPError(Exception):
    """Base exception for ZulipChat MCP."""

    def __init__(
        self, message: str = "An error occurred", details: dict[str, Any] | None = None
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message)
        self.details = details or {}


class ConfigurationError(ZulipMCPError):
    """Configuration related errors."""

    def __init__(self, message: str = "Configuration error") -> None:
        """Initialize configuration error."""
        super().__init__(message)


class ConnectionError(ZulipMCPError):
    """Zulip connection errors."""

    def __init__(self, message: str = "Connection error") -> None:
        """Initialize connection error."""
        super().__init__(message)


class ValidationError(ZulipMCPError):
    """Input validation errors."""

    def __init__(self, message: str = "Validation error") -> None:
        """Initialize validation error."""
        super().__init__(message)


class RateLimitError(ZulipMCPError):
    """Rate limiting errors."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: int | None = None
    ) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds until the rate limit resets
        """
        super().__init__(message, {"retry_after": retry_after})
        self.retry_after = retry_after


class AuthenticationError(ZulipMCPError):
    """Authentication related errors."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize authentication error."""
        super().__init__(message)


class NotFoundError(ZulipMCPError):
    """Resource not found errors."""

    def __init__(self, resource: str = "Resource") -> None:
        """Initialize not found error.

        Args:
            resource: Name of the resource that was not found
        """
        super().__init__(f"{resource} not found")
        self.resource = resource


class PermissionError(ZulipMCPError):
    """Permission denied errors."""

    def __init__(self, action: str = "perform this action") -> None:
        """Initialize permission error.

        Args:
            action: The action that was denied
        """
        super().__init__(f"Permission denied to {action}")
        self.action = action


def create_error_response(
    error: Exception, operation: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create standardized error response.

    Args:
        error: The exception that occurred
        operation: The operation that failed
        details: Additional error details

    Returns:
        Standardized error response dictionary
    """
    response = {
        "status": "error",
        "operation": operation,
        "error": str(error),
        "error_type": type(error).__name__,
        "timestamp": datetime.now().isoformat(),
    }

    if details:
        response["details"] = details

    # Don't expose sensitive information
    if isinstance(error, ConnectionError):
        response["error"] = "Connection failed. Please check your configuration."
    elif isinstance(error, ValidationError):
        response["error"] = str(error)  # Safe to expose
    else:
        response["error"] = "An unexpected error occurred"

    return response
