"""Custom exceptions for ZulipChat MCP Server."""

from typing import Any, Optional


class ZulipMCPError(Exception):
    """Base exception for ZulipChat MCP."""
    
    def __init__(
        self, 
        message: str = "An error occurred", 
        details: Optional[dict[str, Any]] = None
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
        self, 
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None
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