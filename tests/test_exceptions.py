"""Tests for exception classes."""

import sys

sys.path.insert(0, "src")

from zulipchat_mcp.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ValidationError,
    ZulipMCPError,
)


class TestExceptions:
    """Test custom exception classes."""

    def test_base_exception(self):
        """Test base ZulipMCPError."""
        error = ZulipMCPError("Test error", {"key": "value"})
        assert str(error) == "Test error"
        assert error.details == {"key": "value"}

        error_no_details = ZulipMCPError("Test error")
        assert error_no_details.details == {}

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Config missing")
        assert str(error) == "Config missing"
        assert isinstance(error, ZulipMCPError)

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, ZulipMCPError)

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid input")
        assert str(error) == "Invalid input"
        assert isinstance(error, ZulipMCPError)

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("Too many requests", retry_after=60)
        assert str(error) == "Too many requests"
        assert error.retry_after == 60
        assert error.details["retry_after"] == 60
        assert isinstance(error, ZulipMCPError)

        error_no_retry = RateLimitError()
        assert error_no_retry.retry_after is None

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Invalid credentials")
        assert str(error) == "Invalid credentials"
        assert isinstance(error, ZulipMCPError)

    def test_not_found_error(self):
        """Test NotFoundError."""
        error = NotFoundError("Stream")
        assert str(error) == "Stream not found"
        assert error.resource == "Stream"
        assert isinstance(error, ZulipMCPError)

    def test_permission_error(self):
        """Test PermissionError."""
        error = PermissionError("delete messages")
        assert str(error) == "Permission denied to delete messages"
        assert error.action == "delete messages"
        assert isinstance(error, ZulipMCPError)

    def test_exception_inheritance(self):
        """Test that all exceptions inherit from base."""
        exceptions = [
            ConfigurationError(),
            ConnectionError(),
            ValidationError(),
            RateLimitError(),
            AuthenticationError(),
            NotFoundError(),
            PermissionError(),
        ]

        for exc in exceptions:
            assert isinstance(exc, ZulipMCPError)
            assert isinstance(exc, Exception)
