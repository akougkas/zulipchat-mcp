"""Targeted tests to raise coverage for security and topics helpers.

Covers:
- secure_log default and custom key redaction paths (core/security.py 180-189)
- project_from_path happy and exception paths (utils/topics.py 11-17)
"""

from __future__ import annotations

import re

from zulipchat_mcp.core.security import (
    rate_limit_decorator,
    sanitize_input,
    secure_log,
    validate_email,
    validate_emoji,
    validate_stream_name,
    validate_topic,
)
from zulipchat_mcp.utils.metrics import metrics
from zulipchat_mcp.utils.topics import (
    project_from_path,
    topic_chat,
    topic_input,
    topic_status,
)


def test_secure_log_redacts_default_sensitive_keys() -> None:
    # Use quoted values to avoid ambiguous parsing across fields
    msg = 'api_key="abcd1234"; password="hunter2"; token = "xyz"; SECRET: token123'
    redacted = secure_log(msg)
    # Ensure all sensitive values are redacted regardless of case or quoting
    assert "abcd1234" not in redacted
    assert "hunter2" not in redacted
    assert "xyz" not in redacted
    assert re.search(r"api_key\s*[:=]\s*\"?\[REDACTED\]\"?", redacted, re.I)
    assert re.search(r"password\s*[:=]\s*\"?\[REDACTED\]\"?", redacted, re.I)
    assert re.search(r"token\s*[:=]\s*\"?\[REDACTED\]\"?", redacted, re.I)
    assert re.search(r"secret\s*[:=]\s*\"?\[REDACTED\]\"?", redacted, re.I)


def test_secure_log_redacts_custom_keys() -> None:
    msg = "session=ok; api_key=exposed; otp: 123456"
    redacted = secure_log(msg, sensitive_keys=["otp", "api_key"])
    assert "exposed" not in redacted
    assert "123456" not in redacted
    assert "session=ok" in redacted


def test_project_from_path_happy_and_exception_paths() -> None:
    assert project_from_path("/home/user/repo") == "repo"

    # Passing an unsupported type triggers exception branch and returns fallback
    class BadPath:
        pass

    assert project_from_path(BadPath()) == "Project"


def test_topic_helpers_shapes() -> None:
    assert topic_input("Repo", "42").startswith("Agents/Input/Repo/")
    assert "/chat/" in topic_chat("Repo", "Copilot", "s1").lower()
    assert topic_status("Copilot").endswith("Copilot")


def test_security_validators_smoke() -> None:
    # Basic validators quick checks
    assert sanitize_input("<b>hi</b>`rm -rf`") == "&lt;b&gt;hi&lt;/b&gt;rm -rf"
    assert validate_stream_name("dev-stream_1.0")
    assert not validate_stream_name("bad/../../name")
    assert validate_topic("Release (v2.5)!?")
    assert not validate_topic("")
    assert validate_emoji("thumbs_up") and not validate_emoji("bad name!")
    assert validate_email("user@example.com") and not validate_email("nope@bad")


def test_rate_limit_decorator_allows_then_blocks() -> None:
    calls = []

    @rate_limit_decorator(max_calls=2, window=60)
    def f(x: int) -> dict:
        calls.append(x)
        return {"status": "ok", "x": x}

    assert f(1)["status"] == "ok"
    assert f(2)["status"] == "ok"
    blocked = f(3)
    assert blocked["status"] == "error" and "rate limit" in blocked["error"].lower()


def test_metrics_histogram_trims_to_last_1000() -> None:
    # Ensure record_histogram trimming branch executes
    metrics.reset()
    for i in range(1005):
        metrics.record_histogram("h", float(i))
    data = metrics.get_metrics()
    # Stored stats are derived from last 1000 values
    stats = data["histograms"]["h"]
    assert stats["count"] == 1000
