"""Basic tests for logging configuration."""

import logging
from unittest.mock import MagicMock, patch

from zulipchat_mcp.logging_config import (
    get_logger,
    log_api_request,
    log_function_call,
    setup_basic_logging,
    setup_structured_logging,
)


class TestSetupBasicLogging:
    """Test basic logging setup."""

    def test_setup_basic_logging_default(self):
        """Test setting up basic logging with defaults."""
        with patch(
            "src.zulipchat_mcp.logging_config.logging.basicConfig"
        ) as mock_config:
            setup_basic_logging()

            mock_config.assert_called_once()
            call_args = mock_config.call_args
            assert call_args[1]["level"] == logging.INFO
            assert "format" in call_args[1]

    def test_setup_basic_logging_debug(self):
        """Test setting up basic logging with DEBUG level."""
        with patch(
            "src.zulipchat_mcp.logging_config.logging.basicConfig"
        ) as mock_config:
            setup_basic_logging("DEBUG")

            mock_config.assert_called_once()
            call_args = mock_config.call_args
            assert call_args[1]["level"] == logging.DEBUG

    def test_setup_basic_logging_error(self):
        """Test setting up basic logging with ERROR level."""
        with patch(
            "src.zulipchat_mcp.logging_config.logging.basicConfig"
        ) as mock_config:
            setup_basic_logging("ERROR")

            mock_config.assert_called_once()
            call_args = mock_config.call_args
            assert call_args[1]["level"] == logging.ERROR


class TestSetupStructuredLogging:
    """Test structured logging setup."""

    @patch("zulipchat_mcp.logging_config.STRUCTLOG_AVAILABLE", False)
    def test_setup_structured_logging_no_structlog(self):
        """Test fallback when structlog is not available."""
        with patch(
            "src.zulipchat_mcp.logging_config.setup_basic_logging"
        ) as mock_basic:
            setup_structured_logging()

            mock_basic.assert_called_once_with("INFO")

    @patch("zulipchat_mcp.logging_config.STRUCTLOG_AVAILABLE", True)
    def test_setup_structured_logging_with_structlog(self):
        """Test setup when structlog is available."""
        with patch("zulipchat_mcp.logging_config.structlog") as mock_structlog:
            with patch("zulipchat_mcp.logging_config.logging.basicConfig"):
                setup_structured_logging("DEBUG")

                # Should configure structlog
                mock_structlog.configure.assert_called_once()


class TestGetLogger:
    """Test logger retrieval."""

    @patch("zulipchat_mcp.logging_config.STRUCTLOG_AVAILABLE", False)
    def test_get_logger_basic(self):
        """Test getting logger without structlog."""
        logger = get_logger("test_module")

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    @patch("zulipchat_mcp.logging_config.STRUCTLOG_AVAILABLE", True)
    def test_get_logger_structured(self):
        """Test getting logger with structlog."""
        with patch("zulipchat_mcp.logging_config.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger

            logger = get_logger("structured_module")

            assert logger == mock_logger
            mock_structlog.get_logger.assert_called_once_with("structured_module")


class TestLogFunctionCall:
    """Test function call logging function."""

    def test_log_function_call_success(self):
        """Test logging successful function call."""
        mock_logger = MagicMock()

        log_function_call(
            logger=mock_logger,
            func_name="test_function",
            args=(1, 2),
            kwargs={"key": "value"},
            result="success",
        )

        # Should log success
        mock_logger.info.assert_called()

    def test_log_function_call_with_error(self):
        """Test logging function call with error."""
        mock_logger = MagicMock()

        error = ValueError("Test error")
        log_function_call(
            logger=mock_logger,
            func_name="failing_function",
            args=(),
            kwargs={},
            error=error,
        )

        # Should log the error
        mock_logger.error.assert_called()

    @patch("zulipchat_mcp.logging_config.STRUCTLOG_AVAILABLE", True)
    def test_log_function_call_with_structlog(self):
        """Test logging with structlog available."""
        mock_logger = MagicMock()

        log_function_call(
            logger=mock_logger, func_name="structured_func", args=(1,), result=42
        )

        # Should use structured logging
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Function call completed" in str(call_args)


class TestLogApiRequest:
    """Test API request logging function."""

    def test_log_api_request_success(self):
        """Test logging successful API request."""
        mock_logger = MagicMock()

        log_api_request(
            logger=mock_logger,
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration=0.5,
        )

        # Should log request
        mock_logger.info.assert_called()

    def test_log_api_request_with_error(self):
        """Test logging API request with error."""
        mock_logger = MagicMock()

        log_api_request(
            logger=mock_logger,
            method="POST",
            endpoint="/api/users",
            status_code=500,
            error="Internal server error",
        )

        # Should log the error
        mock_logger.error.assert_called()

    @patch("zulipchat_mcp.logging_config.STRUCTLOG_AVAILABLE", True)
    def test_log_api_request_with_structlog(self):
        """Test logging API request with structlog."""
        mock_logger = MagicMock()

        log_api_request(
            logger=mock_logger,
            method="DELETE",
            endpoint="/api/users/123",
            status_code=204,
        )

        # Should use structured logging
        mock_logger.info.assert_called_once()
