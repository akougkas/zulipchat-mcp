"""Tests for the simplified metrics module used in v2.5.0."""

import time
from datetime import datetime

from zulipchat_mcp.metrics import MetricsCollector, metrics


class TestMetricsCollector:
    """Exercise the implemented metrics API (no labels/percentiles)."""

    def test_init_and_basic_ops(self) -> None:
        c = MetricsCollector()
        assert isinstance(c.counters, dict)
        assert isinstance(c.gauges, dict)
        assert isinstance(c.histograms, dict)
        c.increment_counter("requests")
        c.increment_counter("requests", 2)
        c.set_gauge("active", 3)
        c.record_histogram("latency", 0.12)
        data = c.get_metrics()
        assert data["counters"]["requests"] == 3
        assert data["gauges"]["active"] == 3
        assert data["histograms"]["latency"]["count"] == 1
        assert data["histograms"]["latency"]["avg"] == 0.12

    def test_histogram_stats(self) -> None:
        c = MetricsCollector()
        for v in [1.0, 2.0, 3.0]:
            c.record_histogram("h", v)
        d = c.get_metrics()["histograms"]["h"]
        assert d["count"] == 3
        assert d["min"] == 1.0
        assert d["max"] == 3.0
        assert d["avg"] == 2.0
        assert d["latest"] == 3.0

    def test_timers(self) -> None:
        c = MetricsCollector()
        c.start_timer("op")
        time.sleep(0.01)
        dur = c.stop_timer("op")
        assert dur is not None and dur >= 0
        d = c.get_metrics()["histograms"]["op_duration"]
        assert d["count"] == 1

    def test_uptime_and_timestamp(self) -> None:
        c = MetricsCollector()
        time.sleep(0.01)
        m = c.get_metrics()
        assert m["uptime_seconds"] >= 0.01
        datetime.fromisoformat(m["timestamp"])  # parses


class TestGlobalMetrics:
    def test_global_instance(self) -> None:
        assert isinstance(metrics, MetricsCollector)
        metrics.increment_counter("global")
        assert metrics.get_metrics()["counters"]["global"] >= 1

