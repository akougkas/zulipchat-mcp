"""Comprehensive tests for metrics collection system."""

import time
from datetime import datetime

from zulipchat_mcp.metrics import (
    MetricsCollector,
    metrics,
)


class TestMetricsCollector:
    """Test metrics collector functionality."""

    def test_metrics_collector_initialization(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector()

        assert collector.start_time is not None
        assert isinstance(collector.counters, dict)
        assert isinstance(collector.gauges, dict)
        assert isinstance(collector.histograms, dict)
        assert len(collector.counters) == 0
        assert len(collector.gauges) == 0
        assert len(collector.histograms) == 0

    def test_increment_counter(self):
        """Test incrementing a counter."""
        collector = MetricsCollector()

        # Initial increment
        collector.increment_counter("test_counter")
        assert collector.counters["test_counter"] == 1

        # Subsequent increment
        collector.increment_counter("test_counter")
        assert collector.counters["test_counter"] == 2

        # Increment with value
        collector.increment_counter("test_counter", 5)
        assert collector.counters["test_counter"] == 7

    def test_increment_counter_with_labels(self):
        """Test incrementing a counter with labels."""
        collector = MetricsCollector()

        collector.increment_counter("requests", 1, {"method": "GET"})
        collector.increment_counter("requests", 1, {"method": "POST"})
        collector.increment_counter("requests", 2, {"method": "GET"})

        assert collector.counters["requests{method=GET}"] == 3
        assert collector.counters["requests{method=POST}"] == 1

    def test_set_gauge(self):
        """Test setting a gauge value."""
        collector = MetricsCollector()

        collector.set_gauge("memory_usage", 1024)
        assert collector.gauges["memory_usage"] == 1024

        # Update gauge
        collector.set_gauge("memory_usage", 2048)
        assert collector.gauges["memory_usage"] == 2048

    def test_set_gauge_with_labels(self):
        """Test setting a gauge with labels."""
        collector = MetricsCollector()

        collector.set_gauge("cpu_usage", 50.5, {"core": "0"})
        collector.set_gauge("cpu_usage", 75.2, {"core": "1"})

        assert collector.gauges["cpu_usage{core=0}"] == 50.5
        assert collector.gauges["cpu_usage{core=1}"] == 75.2

    def test_record_histogram(self):
        """Test recording histogram values."""
        collector = MetricsCollector()

        # Record multiple values
        values = [10, 20, 30, 40, 50]
        for v in values:
            collector.record_histogram("response_time", v)

        assert "response_time" in collector.histograms
        assert collector.histograms["response_time"] == values

    def test_record_histogram_with_labels(self):
        """Test recording histogram with labels."""
        collector = MetricsCollector()

        collector.record_histogram("latency", 100, {"endpoint": "/api/users"})
        collector.record_histogram("latency", 200, {"endpoint": "/api/posts"})
        collector.record_histogram("latency", 150, {"endpoint": "/api/users"})

        assert collector.histograms["latency{endpoint=/api/users}"] == [100, 150]
        assert collector.histograms["latency{endpoint=/api/posts}"] == [200]

    def test_histogram_memory_limit(self):
        """Test that histograms don't grow indefinitely."""
        collector = MetricsCollector()

        # Record more than 1000 values
        for i in range(1100):
            collector.record_histogram("test_histogram", i)

        # Should keep only last 1000 values
        assert len(collector.histograms["test_histogram"]) == 1000
        assert (
            collector.histograms["test_histogram"][0] == 100
        )  # First value should be 100
        assert (
            collector.histograms["test_histogram"][-1] == 1099
        )  # Last value should be 1099

    def test_make_key(self):
        """Test metric key generation."""
        collector = MetricsCollector()

        # Without labels
        key = collector._make_key("metric_name", None)
        assert key == "metric_name"

        # With labels
        key = collector._make_key(
            "metric_name", {"label1": "value1", "label2": "value2"}
        )
        assert key == "metric_name{label1=value1,label2=value2}"

        # Labels should be sorted
        key1 = collector._make_key("metric", {"b": "2", "a": "1"})
        key2 = collector._make_key("metric", {"a": "1", "b": "2"})
        assert key1 == key2

    def test_get_metrics(self):
        """Test getting all metrics."""
        collector = MetricsCollector()

        # Set up various metrics
        collector.increment_counter("messages_sent", 10)
        collector.set_gauge("active_users", 5)
        collector.record_histogram("latency", 100)
        collector.record_histogram("latency", 200)

        metrics_data = collector.get_metrics()

        # Check basic structure
        assert "uptime_seconds" in metrics_data
        assert metrics_data["uptime_seconds"] >= 0
        assert "timestamp" in metrics_data

        # Check counters
        assert "counters" in metrics_data
        assert metrics_data["counters"]["messages_sent"] == 10

        # Check gauges
        assert "gauges" in metrics_data
        assert metrics_data["gauges"]["active_users"] == 5

        # Check histograms
        assert "histograms" in metrics_data
        assert "latency" in metrics_data["histograms"]
        assert metrics_data["histograms"]["latency"]["count"] == 2
        assert metrics_data["histograms"]["latency"]["mean"] == 150.0
        assert metrics_data["histograms"]["latency"]["min"] == 100
        assert metrics_data["histograms"]["latency"]["max"] == 200
        assert (
            metrics_data["histograms"]["latency"]["p50"] == 200
        )  # Median of [100, 200]

    def test_get_metrics_empty(self):
        """Test getting metrics when empty."""
        collector = MetricsCollector()

        metrics_data = collector.get_metrics()

        assert "uptime_seconds" in metrics_data
        assert "timestamp" in metrics_data
        assert metrics_data["counters"] == {}
        assert metrics_data["gauges"] == {}
        assert metrics_data["histograms"] == {}

    def test_histogram_statistics(self):
        """Test histogram statistical calculations."""
        collector = MetricsCollector()

        # Test with single value
        collector.record_histogram("single", 42)
        metrics_data = collector.get_metrics()

        single_stats = metrics_data["histograms"]["single"]
        assert single_stats["count"] == 1
        assert single_stats["mean"] == 42.0
        assert single_stats["min"] == 42
        assert single_stats["max"] == 42
        assert single_stats["p50"] == 42
        assert single_stats["p95"] == 42
        assert single_stats["p99"] == 42

        # Test with multiple values
        collector = MetricsCollector()
        for i in range(100):
            collector.record_histogram("percentiles", i)

        metrics_data = collector.get_metrics()
        percentile_stats = metrics_data["histograms"]["percentiles"]

        assert percentile_stats["count"] == 100
        assert percentile_stats["min"] == 0
        assert percentile_stats["max"] == 99
        assert percentile_stats["mean"] == 49.5
        assert percentile_stats["p50"] == 50
        assert percentile_stats["p95"] == 95
        assert percentile_stats["p99"] == 99


class TestGlobalMetrics:
    """Test the global metrics instance."""

    def test_global_metrics_instance(self):
        """Test that global metrics instance is available."""
        assert metrics is not None
        assert isinstance(metrics, MetricsCollector)

    def test_global_metrics_operations(self):
        """Test operations on global metrics instance."""
        # Perform operations
        metrics.increment_counter("global_counter", 5)
        metrics.set_gauge("global_gauge", 100)
        metrics.record_histogram("global_histogram", 50)

        # Check full metrics
        metrics_data = metrics.get_metrics()
        assert "global_counter" in metrics_data["counters"]
        assert "global_gauge" in metrics_data["gauges"]
        assert "global_histogram" in metrics_data["histograms"]


class TestIntegration:
    """Integration tests for metrics system."""

    def test_metrics_collection_integration(self):
        """Test complete metrics collection workflow."""
        collector = MetricsCollector()

        # Simulate application metrics
        for i in range(10):
            collector.increment_counter("requests")

            # Simulate varying response times
            response_time = 100 + i * 10
            collector.record_histogram("response_time", response_time)

            # Update active connections gauge
            collector.set_gauge("active_connections", i + 1)

        # Add some labeled metrics
        collector.increment_counter("errors", 1, {"type": "timeout"})
        collector.increment_counter("errors", 2, {"type": "rate_limit"})

        # Get comprehensive metrics
        metrics_data = collector.get_metrics()

        # Verify counters
        assert metrics_data["counters"]["requests"] == 10
        assert metrics_data["counters"]["errors{type=timeout}"] == 1
        assert metrics_data["counters"]["errors{type=rate_limit}"] == 2

        # Verify gauges
        assert metrics_data["gauges"]["active_connections"] == 10

        # Verify histograms
        response_stats = metrics_data["histograms"]["response_time"]
        assert response_stats["count"] == 10
        assert response_stats["min"] == 100
        assert response_stats["max"] == 190
        assert response_stats["mean"] == 145.0

        # Verify uptime
        assert metrics_data["uptime_seconds"] > 0

    def test_concurrent_metrics_operations(self):
        """Test thread-safety of metrics operations."""
        import threading

        collector = MetricsCollector()

        def increment_counter():
            for _ in range(100):
                collector.increment_counter("concurrent_counter")

        def record_values():
            for i in range(100):
                collector.record_histogram("concurrent_histogram", i)

        def update_gauge():
            for i in range(100):
                collector.set_gauge("concurrent_gauge", i)

        # Start multiple threads
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=increment_counter))
            threads.append(threading.Thread(target=record_values))
            threads.append(threading.Thread(target=update_gauge))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify metrics
        metrics_data = collector.get_metrics()

        # Should have 300 increments (3 threads × 100)
        assert metrics_data["counters"]["concurrent_counter"] == 300

        # Should have 300 histogram values
        assert metrics_data["histograms"]["concurrent_histogram"]["count"] == 300

        # Gauge should have last value (99)
        assert metrics_data["gauges"]["concurrent_gauge"] == 99

    def test_metrics_with_various_labels(self):
        """Test metrics collection with various label combinations."""
        collector = MetricsCollector()

        # HTTP requests with method and status
        collector.increment_counter(
            "http_requests", 1, {"method": "GET", "status": "200"}
        )
        collector.increment_counter(
            "http_requests", 1, {"method": "GET", "status": "404"}
        )
        collector.increment_counter(
            "http_requests", 1, {"method": "POST", "status": "201"}
        )
        collector.increment_counter(
            "http_requests", 1, {"method": "GET", "status": "200"}
        )

        # Response times per endpoint
        collector.record_histogram("response_time_ms", 100, {"endpoint": "/api/users"})
        collector.record_histogram("response_time_ms", 150, {"endpoint": "/api/users"})
        collector.record_histogram("response_time_ms", 200, {"endpoint": "/api/posts"})

        # Memory usage per service
        collector.set_gauge("memory_mb", 512, {"service": "api"})
        collector.set_gauge("memory_mb", 256, {"service": "worker"})

        metrics_data = collector.get_metrics()

        # Check HTTP requests
        assert metrics_data["counters"]["http_requests{method=GET,status=200}"] == 2
        assert metrics_data["counters"]["http_requests{method=GET,status=404}"] == 1
        assert metrics_data["counters"]["http_requests{method=POST,status=201}"] == 1

        # Check response times
        assert (
            metrics_data["histograms"]["response_time_ms{endpoint=/api/users}"]["count"]
            == 2
        )
        assert (
            metrics_data["histograms"]["response_time_ms{endpoint=/api/users}"]["mean"]
            == 125.0
        )
        assert (
            metrics_data["histograms"]["response_time_ms{endpoint=/api/posts}"]["count"]
            == 1
        )

        # Check memory gauges
        assert metrics_data["gauges"]["memory_mb{service=api}"] == 512
        assert metrics_data["gauges"]["memory_mb{service=worker}"] == 256

    def test_metrics_collector_uptime(self):
        """Test that uptime is calculated correctly."""
        collector = MetricsCollector()

        # Wait a bit
        time.sleep(0.1)

        metrics_data = collector.get_metrics()

        # Uptime should be at least 0.1 seconds
        assert metrics_data["uptime_seconds"] >= 0.1
        assert metrics_data["uptime_seconds"] < 1.0  # But not too much

    def test_metrics_timestamp_format(self):
        """Test that timestamp is in ISO format."""
        collector = MetricsCollector()

        metrics_data = collector.get_metrics()

        # Should be able to parse the timestamp
        timestamp_str = metrics_data["timestamp"]
        parsed = datetime.fromisoformat(timestamp_str)
        assert parsed is not None

        # Should be recent
        now = datetime.now()
        diff = abs((now - parsed).total_seconds())
        assert diff < 1.0  # Within 1 second
