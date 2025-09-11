"""Tests for utils.logging basic flows without requiring structlog."""

from __future__ import annotations

from zulipchat_mcp.utils.logging import (
    setup_basic_logging,
    get_logger,
    LogContext,
    log_function_call,
    log_api_request,
)


def test_logging_helpers_basic() -> None:
    setup_basic_logging("INFO")
    logger = get_logger(__name__)

    # Context manager should return a logger instance
    with LogContext(logger, tool="test") as bound:
        # Log success and error paths
        log_function_call(bound, "demo_func", args=(1, 2), kwargs={"a": 1}, result=123)
        try:
            raise ValueError("boom")
        except Exception as e:
            log_function_call(bound, "demo_func", error=e)

        # API request logging
        log_api_request(bound, "GET", "/api", status_code=200, duration=0.01)
        log_api_request(bound, "POST", "/api", status_code=500, error="fail")

