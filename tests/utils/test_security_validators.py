"""Security validator smoke tests."""

from __future__ import annotations

from zulipchat_mcp.core.security import (
    validate_email,
    validate_emoji,
)
from zulipchat_mcp.utils.metrics import metrics


def test_security_validators_smoke() -> None:
    # Basic validators quick checks
    assert validate_emoji("thumbs_up") and not validate_emoji("bad name!")
    assert validate_email("user@example.com") and not validate_email("nope@bad")


def test_metrics_histogram_trims_to_last_1000() -> None:
    # Ensure record_histogram trimming branch executes
    metrics.reset()
    for i in range(1005):
        metrics.record_histogram("h", float(i))
    data = metrics.get_metrics()
    # Stored stats are derived from last 1000 values
    stats = data["histograms"]["h"]
    assert stats["count"] == 1000
