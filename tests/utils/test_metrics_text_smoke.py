from __future__ import annotations

from zulipchat_mcp.utils.metrics import (
    Timer,
    get_metrics_text,
    metrics,
    track_tool_call,
    track_tool_error,
)


def test_metrics_text_smoke() -> None:
    metrics.reset()
    track_tool_call("x")
    track_tool_error("x", "ValueError")
    with Timer("zulip_mcp_api_request_duration_seconds", {"tool": "x"}):
        pass
    text = get_metrics_text()
    # Ensure key sections present
    assert "uptime_seconds" in text
    assert "zulip_mcp_tool_calls_total{tool=x}" in text
    # Depending on label ordering, error_type may appear before tool
    assert "zulip_mcp_tool_errors_total" in text and "ValueError" in text
