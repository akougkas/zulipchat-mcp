"""Tests for utils.logging basic flows without requiring structlog."""

from __future__ import annotations

from zulipchat_mcp.utils.logging import (
    LogContext,
    get_logger,
    setup_basic_logging,
    setup_structured_logging,
)


def test_logging_helpers_basic() -> None:
    setup_basic_logging("INFO")
    logger = get_logger(__name__)

    # Context manager should return a logger instance
    with LogContext(logger, tool="test") as bound:
        bound.info("ok")

    # Structured logging setup path
    setup_structured_logging("INFO")
