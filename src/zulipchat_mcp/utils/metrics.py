"""Metrics collection for ZulipChat MCP Server."""

import time
from collections import defaultdict
from datetime import datetime
from typing import Any


class MetricsCollector:
    """Simple metrics collector without external dependencies."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.counters: dict[str, int] = defaultdict(int)
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.gauges: dict[str, float] = {}
        self.start_time = time.time()

    def increment_counter(
        self, name: str, value: int = 1, labels: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Value to increment by
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self.counters[key] += value

    def record_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Record a histogram value.

        Args:
            name: Metric name
            value: Value to record
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self.histograms[key].append(value)
        # Keep only last 1000 values to prevent memory issues
        if len(self.histograms[key]) > 1000:
            self.histograms[key] = self.histograms[key][-1000:]

    def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Set a gauge value.

        Args:
            name: Metric name
            value: Value to set
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self.gauges[key] = value

    def _make_key(self, name: str, labels: dict[str, str] | None = None) -> str:
        """Create metric key from name and labels.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Metric key
        """
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_metrics(self) -> dict[str, Any]:
        """Get all metrics.

        Returns:
            Dictionary of all metrics
        """
        uptime = time.time() - self.start_time

        # Calculate histogram stats
        histogram_stats = {}
        for key, values in self.histograms.items():
            if values:
                sorted_values = sorted(values)
                histogram_stats[key] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "p50": sorted_values[len(sorted_values) // 2],
                    "p95": sorted_values[int(len(sorted_values) * 0.95)],
                    "p99": sorted_values[int(len(sorted_values) * 0.99)],
                }

        return {
            "uptime_seconds": uptime,
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": histogram_stats,
            "timestamp": datetime.now().isoformat(),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()
        self.start_time = time.time()


# Global metrics collector instance
metrics = MetricsCollector()


# Metric names
TOOL_CALLS_TOTAL = "zulip_mcp_tool_calls_total"
TOOL_DURATION_SECONDS = "zulip_mcp_tool_duration_seconds"
TOOL_ERRORS_TOTAL = "zulip_mcp_tool_errors_total"
ACTIVE_CONNECTIONS = "zulip_mcp_active_connections"
CACHE_HITS_TOTAL = "zulip_mcp_cache_hits_total"
CACHE_MISSES_TOTAL = "zulip_mcp_cache_misses_total"
MESSAGE_SENT_TOTAL = "zulip_mcp_messages_sent_total"
MESSAGE_RECEIVED_TOTAL = "zulip_mcp_messages_received_total"
API_REQUEST_DURATION_SECONDS = "zulip_mcp_api_request_duration_seconds"
API_REQUEST_TOTAL = "zulip_mcp_api_requests_total"


class Timer:
    """Context manager for timing operations."""

    def __init__(self, metric_name: str, labels: dict[str, str] | None = None) -> None:
        """Initialize timer.

        Args:
            metric_name: Name of the metric to record
            labels: Optional labels
        """
        self.metric_name = metric_name
        self.labels = labels
        self.start_time: float | None = None

    def __enter__(self) -> "Timer":
        """Start timer."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timer and record duration."""
        if self.start_time:
            duration = time.time() - self.start_time
            metrics.record_histogram(self.metric_name, duration, self.labels)


def track_tool_call(tool_name: str) -> None:
    """Track a tool call.

    Args:
        tool_name: Name of the tool
    """
    metrics.increment_counter(TOOL_CALLS_TOTAL, labels={"tool": tool_name})


def track_tool_error(tool_name: str, error_type: str) -> None:
    """Track a tool error.

    Args:
        tool_name: Name of the tool
        error_type: Type of error
    """
    metrics.increment_counter(
        TOOL_ERRORS_TOTAL, labels={"tool": tool_name, "error_type": error_type}
    )


def track_cache_hit(cache_type: str) -> None:
    """Track a cache hit.

    Args:
        cache_type: Type of cache
    """
    metrics.increment_counter(CACHE_HITS_TOTAL, labels={"cache": cache_type})


def track_cache_miss(cache_type: str) -> None:
    """Track a cache miss.

    Args:
        cache_type: Type of cache
    """
    metrics.increment_counter(CACHE_MISSES_TOTAL, labels={"cache": cache_type})


def track_message_sent(message_type: str) -> None:
    """Track a sent message.

    Args:
        message_type: Type of message (stream/private)
    """
    metrics.increment_counter(MESSAGE_SENT_TOTAL, labels={"type": message_type})


def track_message_received(stream: str) -> None:
    """Track received messages.

    Args:
        stream: Stream name
    """
    metrics.increment_counter(MESSAGE_RECEIVED_TOTAL, labels={"stream": stream})


def set_active_connections(count: int) -> None:
    """Set the number of active connections.

    Args:
        count: Number of active connections
    """
    metrics.set_gauge(ACTIVE_CONNECTIONS, float(count))


def get_metrics_text() -> str:
    """Get metrics in text format.

    Returns:
        Metrics in text format
    """
    data = metrics.get_metrics()
    lines = []

    # Format uptime
    lines.append("# HELP uptime_seconds Time since server started")
    lines.append("# TYPE uptime_seconds gauge")
    lines.append(f"uptime_seconds {data['uptime_seconds']:.2f}")
    lines.append("")

    # Format counters
    for key, value in data["counters"].items():
        lines.append(f"# TYPE {key.split('{')[0]} counter")
        lines.append(f"{key} {value}")
    lines.append("")

    # Format gauges
    for key, value in data["gauges"].items():
        lines.append(f"# TYPE {key.split('{')[0]} gauge")
        lines.append(f"{key} {value}")
    lines.append("")

    # Format histograms
    for key, stats in data["histograms"].items():
        base_name = key.split("{")[0]
        lines.append(f"# TYPE {base_name} histogram")
        lines.append(f"{key}_count {stats['count']}")
        lines.append(f"{key}_min {stats['min']:.4f}")
        lines.append(f"{key}_max {stats['max']:.4f}")
        lines.append(f"{key}_mean {stats['mean']:.4f}")
        lines.append(f"{key}_p50 {stats['p50']:.4f}")
        lines.append(f"{key}_p95 {stats['p95']:.4f}")
        lines.append(f"{key}_p99 {stats['p99']:.4f}")

    return "\n".join(lines)
