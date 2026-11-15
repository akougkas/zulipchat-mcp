"""Additional tests for core.security module."""

from __future__ import annotations

from zulipchat_mcp.core.security import (
    validate_email,
    validate_emoji,
)


def test_sanitize_and_validators() -> None:
    assert validate_emoji("thumbs_up") is True
    assert validate_emoji("bad-emoji!") is False

    assert validate_email("user@example.com") is True
    assert validate_email("nope") is False
