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
        handlers=[logging.StreamHandler(sys.stdout)],
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


def log_function_call(
    logger: Any,
    func_name: str,
    args: tuple | None = None,
    kwargs: dict | None = None,
    result: Any = None,
    error: Exception | None = None,
) -> None:
    """Log a function call with parameters and result.

    Args:
        logger: Logger instance
        func_name: Name of the function
        args: Function arguments
        kwargs: Function keyword arguments
        result: Function result
        error: Exception if function failed
    """
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}

    log_data: dict[str, Any] = {
        "function": func_name,
        "args": str(args)[:200],  # Truncate long args
        "kwargs": str(kwargs)[:200],
    }

    if error:
        log_data["error"] = str(error)
        log_data["error_type"] = type(error).__name__
        if STRUCTLOG_AVAILABLE:
            logger.error("Function call failed", **log_data)
        else:
            logger.error(f"Function {func_name} failed: {error}")
    else:
        log_data["result_type"] = type(result).__name__
        if STRUCTLOG_AVAILABLE:
            logger.info("Function call completed", **log_data)
        else:
            logger.info(f"Function {func_name} completed successfully")


def log_api_request(
    logger: Any,
    method: str,
    endpoint: str,
    status_code: int | None = None,
    duration: float | None = None,
    error: str | None = None,
) -> None:
    """Log an API request.

    Args:
        logger: Logger instance
        method: HTTP method
        endpoint: API endpoint
        status_code: Response status code
        duration: Request duration in seconds
        error: Error message if request failed
    """
    log_data: dict[str, Any] = {
        "method": method,
        "endpoint": endpoint,
    }

    if status_code:
        log_data["status_code"] = status_code
    if duration:
        log_data["duration_ms"] = round(duration * 1000, 2)
    if error:
        log_data["error"] = error

    if STRUCTLOG_AVAILABLE:
        if error or (status_code and status_code >= 400):
            logger.error("API request failed", **log_data)
        else:
            logger.info("API request completed", **log_data)
    else:
        if error or (status_code and status_code >= 400):
            logger.error(f"API {method} {endpoint} failed: {error or status_code}")
        else:
            logger.info(f"API {method} {endpoint} completed: {status_code}")


# Initialize default logger
default_logger = get_logger(__name__)
