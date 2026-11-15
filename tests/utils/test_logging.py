"""Tests for utils/logging.py."""

import logging
from unittest.mock import ANY, MagicMock, patch

from src.zulipchat_mcp.utils import logging as logging_utils


class TestLogging:
    """Tests for logging utilities."""

    def test_setup_basic_logging(self):
        """Test basic logging setup."""
        with patch("logging.basicConfig") as mock_basic_config:
            logging_utils.setup_basic_logging("DEBUG")
            mock_basic_config.assert_called_with(
                level=logging.DEBUG, format=ANY, handlers=ANY
            )

    def test_setup_structured_logging_with_structlog(self):
        """Test structured logging setup when structlog is available."""
        # Assuming structlog is installed in env
        with (
            patch("structlog.configure") as mock_configure,
            patch("logging.basicConfig") as mock_basic_config,
            patch("src.zulipchat_mcp.utils.logging.STRUCTLOG_AVAILABLE", True),
        ):

            logging_utils.setup_structured_logging("INFO")
            mock_configure.assert_called()
            mock_basic_config.assert_called()

    def test_setup_structured_logging_without_structlog(self):
        """Test structured logging setup falls back when structlog unavailable."""
        with (
            patch("src.zulipchat_mcp.utils.logging.STRUCTLOG_AVAILABLE", False),
            patch("src.zulipchat_mcp.utils.logging.setup_basic_logging") as mock_basic,
        ):

            logging_utils.setup_structured_logging("INFO")
            mock_basic.assert_called_with("INFO")

    def test_get_logger(self):
        """Test get_logger returns logger."""
        logger = logging_utils.get_logger("test_logger")
        assert logger is not None

    def test_log_context(self):
        """Test LogContext context manager."""
        logger = MagicMock()

        # With structlog (bind available)
        with patch("src.zulipchat_mcp.utils.logging.STRUCTLOG_AVAILABLE", True):
            logger.bind.return_value = "bound_logger"
            with logging_utils.LogContext(logger, key="value") as ctx:
                assert ctx == "bound_logger"
                logger.bind.assert_called_with(key="value")

        # Without structlog
        with patch("src.zulipchat_mcp.utils.logging.STRUCTLOG_AVAILABLE", False):
            with logging_utils.LogContext(logger, key="value") as ctx:
                assert ctx == logger
