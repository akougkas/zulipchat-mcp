"""Metrics collection system for ZulipChat MCP."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from typing import Any


class MetricsCollector:
    """Collects and manages metrics for the application."""
    
    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self.start_time = time.time()
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.timers: dict[str, float] = {}
        
    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter metric.
        
        Args:
            name: Counter name
            value: Amount to increment
        """
        self.counters[name] += value
        
    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric.
        
        Args:
            name: Gauge name
            value: Gauge value
        """
        self.gauges[name] = value
        
    def record_histogram(self, name: str, value: float) -> None:
        """Record a value in a histogram.
        
        Args:
            name: Histogram name
            value: Value to record
        """
        self.histograms[name].append(value)
        
    def start_timer(self, name: str) -> None:
        """Start a timer.
        
        Args:
            name: Timer name
        """
        self.timers[name] = time.time()
        
    def stop_timer(self, name: str) -> float | None:
        """Stop a timer and record the duration.
        
        Args:
            name: Timer name
            
        Returns:
            Duration in seconds, or None if timer not started
        """
        if name not in self.timers:
            return None
            
        duration = time.time() - self.timers[name]
        self.record_histogram(f"{name}_duration", duration)
        del self.timers[name]
        return duration
        
    def get_metrics(self) -> dict[str, Any]:
        """Get all metrics.
        
        Returns:
            Dictionary containing all metrics
        """
        uptime = time.time() - self.start_time
        
        # Calculate histogram stats
        histogram_stats = {}
        for name, values in self.histograms.items():
            if values:
                histogram_stats[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "latest": values[-1] if values else None,
                }
            else:
                histogram_stats[name] = {
                    "count": 0,
                    "min": None,
                    "max": None,
                    "avg": None,
                    "latest": None,
                }
        
        return {
            "uptime_seconds": uptime,
            "timestamp": datetime.now().isoformat(),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": histogram_stats,
            "active_timers": list(self.timers.keys()),
        }
    
    def reset(self) -> None:
        """Reset all metrics except uptime."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.timers.clear()


# Global metrics instance
metrics = MetricsCollector()