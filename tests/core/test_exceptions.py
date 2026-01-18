"""Tests for core/exceptions.py."""

import pytest
from datetime import datetime
from src.zulipchat_mcp.core.exceptions import (
    ZulipMCPError,
    ConfigurationError,
    ConnectionError,
    ValidationError,
    RateLimitError,
    AuthenticationError,
    NotFoundError,
    PermissionError,
    CircuitBreakerOpenError,
    create_error_response,
)


class TestZulipMCPError:
    """Tests for base ZulipMCPError."""

    def test_init_default(self):
        """Test initialization with default values."""
        error = ZulipMCPError()
        assert str(error) == "An error occurred"
        assert error.details == {}

    def test_init_custom(self):
        """Test initialization with custom values."""
        details = {"key": "value"}
        error = ZulipMCPError("Custom message", details)
        assert str(error) == "Custom message"
        assert error.details == details


class TestSpecificErrors:
    """Tests for specific error subclasses."""

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Config bad")
        assert str(error) == "Config bad"
        assert isinstance(error, ZulipMCPError)

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Connect bad")
        assert str(error) == "Connect bad"
        assert isinstance(error, ZulipMCPError)

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid input")
        assert str(error) == "Invalid input"
        assert isinstance(error, ZulipMCPError)

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("Slow down", retry_after=60)
        assert str(error) == "Slow down"
        assert error.retry_after == 60
        assert error.details == {"retry_after": 60}
        assert isinstance(error, ZulipMCPError)

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Auth failed")
        assert str(error) == "Auth failed"
        assert isinstance(error, ZulipMCPError)

    def test_not_found_error(self):
        """Test NotFoundError."""
        error = NotFoundError("Message")
        assert str(error) == "Message not found"
        assert error.resource == "Message"
        assert isinstance(error, ZulipMCPError)

    def test_permission_error(self):
        """Test PermissionError."""
        error = PermissionError("edit")
        assert str(error) == "Permission denied to edit"
        assert error.action == "edit"
        assert isinstance(error, ZulipMCPError)

    def test_circuit_breaker_open_error(self):
        """Test CircuitBreakerOpenError."""
        error = CircuitBreakerOpenError("Circuit open", service="zulip")
        assert str(error) == "Circuit open"
        assert error.details == {"service": "zulip"}
        assert isinstance(error, ZulipMCPError)


class TestCreateErrorResponse:
    """Tests for create_error_response helper."""

    def test_create_error_response_generic(self):
        """Test creating response for generic exception."""
        error = Exception("Something went wrong")
        response = create_error_response(error, "test_op")
        
        assert response["status"] == "error"
        assert response["operation"] == "test_op"
        assert response["error"] == "An unexpected error occurred"
        assert response["error_type"] == "Exception"
        assert "timestamp" in response

    def test_create_error_response_validation(self):
        """Test creating response for ValidationError (safe to expose)."""
        error = ValidationError("Invalid ID")
        response = create_error_response(error, "validate_id")
        
        assert response["error"] == "Invalid ID"
        assert response["error_type"] == "ValidationError"

    def test_create_error_response_connection(self):
        """Test creating response for ConnectionError (masked)."""
        error = ConnectionError("Connection refused to 127.0.0.1")
        response = create_error_response(error, "connect")
        
        assert response["error"] == "Connection failed. Please check your configuration."
        assert response["error_type"] == "ConnectionError"

    def test_create_error_response_with_details(self):
        """Test creating response with additional details."""
        error = Exception("Error")
        details = {"extra": "info"}
        response = create_error_response(error, "op", details)
        
        assert response["details"] == details
