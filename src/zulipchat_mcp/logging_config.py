"""Logging configuration for ZulipChat MCP."""

from __future__ import annotations

import logging
import sys
from typing import Any

# Check if structlog is available
try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


def setup_basic_logging(
    level: int = logging.INFO,
    format_string: str | None = None,
) -> None:
    """Set up basic Python logging.
    
    Args:
        level: Logging level
        format_string: Format string for log messages
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=level,
        format=format_string,
        stream=sys.stderr,
    )


def setup_structured_logging() -> None:
    """Set up structured logging with structlog if available."""
    if not STRUCTLOG_AVAILABLE:
        setup_basic_logging()
        return
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(),
    ]
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> logging.Logger | Any:
    """Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def log_function_call(
    logger: logging.Logger | Any,
    function_name: str,
    **kwargs: Any,
) -> None:
    """Log a function call with parameters.
    
    Args:
        logger: Logger instance
        function_name: Name of the function
        **kwargs: Function parameters
    """
    if STRUCTLOG_AVAILABLE and hasattr(logger, "info"):
        logger.info("function_call", function=function_name, **kwargs)
    else:
        logger.info(f"Function call: {function_name}", extra=kwargs)


def log_api_request(
    logger: logging.Logger | Any,
    method: str,
    endpoint: str,
    status_code: int | None = None,
    **kwargs: Any,
) -> None:
    """Log an API request.
    
    Args:
        logger: Logger instance
        method: HTTP method
        endpoint: API endpoint
        status_code: Response status code
        **kwargs: Additional parameters
    """
    if STRUCTLOG_AVAILABLE and hasattr(logger, "info"):
        logger.info(
            "api_request",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            **kwargs,
        )
    else:
        msg = f"API request: {method} {endpoint}"
        if status_code:
            msg += f" -> {status_code}"
        logger.info(msg, extra=kwargs)