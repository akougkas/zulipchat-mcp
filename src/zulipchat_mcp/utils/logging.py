"""Structured logging configuration for ZulipChat MCP Server."""

import logging
import sys
from typing import Any

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    structlog = None  # type: ignore
    STRUCTLOG_AVAILABLE = False


def setup_basic_logging(level: str = "INFO") -> None:
    """Set up basic logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure structured logging with structlog if available.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if not STRUCTLOG_AVAILABLE:
        setup_basic_logging(level)
        return

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                ]
            ),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set up stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper()),
    )


def get_logger(name: str) -> Any:
    """Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance (structlog or stdlib)
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding contextual information to logs."""

    def __init__(self, logger: Any, **kwargs: Any) -> None:
        """Initialize log context.

        Args:
            logger: Logger instance
            **kwargs: Context key-value pairs
        """
        self.logger = logger
        self.context = kwargs
        self.bound_logger = None

    def __enter__(self) -> Any:
        """Enter context and bind logger."""
        if STRUCTLOG_AVAILABLE and hasattr(self.logger, "bind"):
            self.bound_logger = self.logger.bind(**self.context)
            return self.bound_logger
        return self.logger

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        pass


# Initialize default logger
