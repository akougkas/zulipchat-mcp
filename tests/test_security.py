"""Tests for security module."""

import sys
import time

sys.path.insert(0, "src")

from zulipchat_mcp.security import (
    RateLimiter,
    sanitize_input,
    secure_log,
    validate_email,
    validate_emoji,
    validate_message_type,
    validate_stream_name,
    validate_topic,
)


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(max_calls=2, window=1)

        # First two calls should pass
        assert limiter.check_rate_limit("client1") is True
        assert limiter.check_rate_limit("client1") is True

        # Third call should be blocked
        assert limiter.check_rate_limit("client1") is False

        # Different client should have its own limit
        assert limiter.check_rate_limit("client2") is True

    def test_rate_limiter_window_expiry(self):
        """Test rate limit window expiration."""
        limiter = RateLimiter(max_calls=1, window=0.5)

        assert limiter.check_rate_limit("client1") is True
        assert limiter.check_rate_limit("client1") is False

        # Wait for window to expire
        time.sleep(0.6)
        assert limiter.check_rate_limit("client1") is True


class TestInputSanitization:
    """Test input sanitization functions."""

    def test_sanitize_input_html_escape(self):
        """Test HTML escaping."""
        dangerous = "<script>alert('xss')</script>"
        safe = sanitize_input(dangerous)
        assert "<script>" not in safe
        assert "&lt;script&gt;" in safe

    def test_sanitize_input_backtick_removal(self):
        """Test backtick removal."""
        dangerous = "`rm -rf /`"
        safe = sanitize_input(dangerous)
        assert "`" not in safe

    def test_sanitize_input_max_length(self):
        """Test max length enforcement."""
        long_input = "a" * 20000
        safe = sanitize_input(long_input, max_length=100)
        assert len(safe) == 100


class TestValidation:
    """Test validation functions."""

    def test_validate_stream_name(self):
        """Test stream name validation."""
        # Valid names
        assert validate_stream_name("general") is True
        assert validate_stream_name("test-stream") is True
        assert validate_stream_name("my_stream") is True
        assert validate_stream_name("stream.name") is True
        assert validate_stream_name("Stream with spaces") is True

        # Invalid names
        assert validate_stream_name("") is False
        assert validate_stream_name("a" * 101) is False
        assert validate_stream_name("stream$name") is False
        assert validate_stream_name("stream@name") is False
        assert validate_stream_name("stream;name") is False

    def test_validate_topic(self):
        """Test topic validation."""
        # Valid topics
        assert validate_topic("general") is True
        assert validate_topic("test-topic") is True
        assert validate_topic("My Topic!") is True
        assert validate_topic("Question?") is True
        assert validate_topic("(Important)") is True

        # Invalid topics
        assert validate_topic("") is False
        assert validate_topic("a" * 201) is False
        assert validate_topic("topic$money") is False
        assert validate_topic("topic@email") is False

    def test_validate_emoji(self):
        """Test emoji name validation."""
        # Valid emoji names
        assert validate_emoji("smile") is True
        assert validate_emoji("thumbs_up") is True
        assert validate_emoji("heart123") is True

        # Invalid emoji names
        assert validate_emoji("") is False
        assert validate_emoji("a" * 51) is False
        assert validate_emoji("emoji-name") is False
        assert validate_emoji("emoji.name") is False
        assert validate_emoji("emoji name") is False

    def test_validate_email(self):
        """Test email validation."""
        # Valid emails
        assert validate_email("user@example.com") is True
        assert validate_email("test.user@example.co.uk") is True
        assert validate_email("user+tag@example.com") is True

        # Invalid emails
        assert validate_email("not_an_email") is False
        assert validate_email("@example.com") is False
        assert validate_email("user@") is False
        assert validate_email("user@example") is False
        assert validate_email("") is False

    def test_validate_message_type(self):
        """Test message type validation."""
        assert validate_message_type("stream") is True
        assert validate_message_type("private") is True
        assert validate_message_type("invalid") is False
        assert validate_message_type("") is False


class TestSecureLogging:
    """Test secure logging functionality."""

    def test_secure_log_redaction(self):
        """Test sensitive data redaction."""
        message = "api_key='secret123' password='pass456'"
        sanitized = secure_log(message)
        assert "secret123" not in sanitized
        assert "pass456" not in sanitized
        assert "[REDACTED]" in sanitized

    def test_secure_log_custom_keys(self):
        """Test custom sensitive keys."""
        message = "custom_secret='sensitive' api_key='key123'"
        sanitized = secure_log(message, sensitive_keys=["custom_secret"])
        assert "sensitive" not in sanitized
        assert "[REDACTED]" in sanitized
        # api_key should not be redacted with custom keys only
        assert "key123" in sanitized

    def test_secure_log_various_formats(self):
        """Test different log formats."""
        # JSON-like format
        message = '{"api_key": "secret", "data": "safe"}'
        sanitized = secure_log(message)
        assert "secret" not in sanitized
        assert "safe" in sanitized

        # Key=value format
        message = "token=abc123"
        sanitized = secure_log(message)
        assert "abc123" not in sanitized
        assert "[REDACTED]" in sanitized
