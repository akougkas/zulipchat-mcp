"""Additional tests for core.security module."""

from __future__ import annotations

import time

from zulipchat_mcp.core.security import (
    rate_limit_decorator,
    sanitize_input,
    validate_email,
    validate_emoji,
    validate_message_type,
    validate_stream_name,
    validate_topic,
)


def test_sanitize_and_validators() -> None:
    text = "<b>hello</b> `rm -rf /`"
    out = sanitize_input(text, max_length=100)
    assert "&lt;b&gt;hello&lt;/b&gt;" in out
    assert "`" not in out

    assert validate_stream_name("general-1") is True
    assert validate_stream_name("bad@name") is False

    assert validate_topic("Topic (1)!") is True
    assert validate_topic("") is False

    assert validate_emoji("thumbs_up") is True
    assert validate_emoji("bad-emoji!") is False

    assert validate_email("user@example.com") is True
    assert validate_email("nope") is False

    assert validate_message_type("stream") is True
    assert validate_message_type("direct") is False


def test_rate_limiter_decorator_allows_then_blocks() -> None:
    @rate_limit_decorator(max_calls=1, window=1)
    def limited():
        return {"status": "ok"}

    first = limited()
    second = limited()
    assert first.get("status") == "ok"
    assert second.get("status") == "error"
    time.sleep(1.1)
    third = limited()
    assert third.get("status") == "ok"
