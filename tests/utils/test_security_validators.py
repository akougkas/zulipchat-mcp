"""Security validator smoke tests."""

from __future__ import annotations

from zulipchat_mcp.core.security import (
    validate_email,
    validate_emoji,
)


def test_security_validators_smoke() -> None:
    # Basic validators quick checks
    assert validate_emoji("thumbs_up") and not validate_emoji("bad name!")
    assert validate_email("user@example.com") and not validate_email("nope@bad")
