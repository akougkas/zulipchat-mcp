"""Basic tests for utils.health public API."""

from __future__ import annotations

import pytest

from zulipchat_mcp.utils.health import (
    health_monitor,
    perform_health_check,
    get_liveness,
    get_readiness,
)


@pytest.mark.asyncio
async def test_perform_health_check_and_readiness_liveness() -> None:
    # Run a health check (may be degraded/unhealthy depending on env, that's ok)
    report = await perform_health_check()
    assert isinstance(report, dict)
    assert "status" in report
    assert "checks" in report

    # Liveness always returns a timestamp
    live = get_liveness()
    assert live["status"] == "alive"

    # Readiness returns a boolean flag
    ready = get_readiness()
    assert isinstance(ready["ready"], bool)

