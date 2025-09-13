"""Tests for utils.metrics: counters, histograms, and text export."""

from __future__ import annotations

import time

from zulipchat_mcp.utils.metrics import (
    Timer,
    get_metrics_text,
    metrics,
    set_active_connections,
    track_cache_hit,
    track_cache_miss,
    track_message_received,
    track_message_sent,
    track_tool_call,
    track_tool_error,
)


def test_metrics_counters_and_gauges_and_timer() -> None:
    metrics.reset()

    # Counters
    track_tool_call("demo.tool")
    track_tool_error("demo.tool", "ValueError")
    track_cache_hit("local")
    track_cache_miss("local")
    track_message_sent("stream")
    track_message_received("general")

    # Gauge
    set_active_connections(3)

    # Histogram via Timer
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "demo.tool"}):
        time.sleep(0.001)

    text = get_metrics_text()

    # Basic assertions on exported metrics text
    assert "uptime_seconds" in text
    assert "zulip_mcp_tool_calls_total{tool=demo.tool}" in text
    assert "zulip_mcp_tool_errors_total{error_type=ValueError,tool=demo.tool}" in text
    assert "zulip_mcp_tool_duration_seconds" in text
    assert "zulip_mcp_active_connections" in text
