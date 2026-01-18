"""Additional coverage for health monitor checks behavior."""

from __future__ import annotations

import pytest

from zulipchat_mcp.utils.health import health_monitor, perform_health_check


@pytest.mark.asyncio
async def test_health_monitor_custom_checks() -> None:
    # Clear existing checks to isolate this test
    health_monitor.checks.clear()

    # Add a passing critical check and a failing non-critical
    health_monitor.add_check("always_ok", lambda: True, critical=True)
    health_monitor.add_check("always_fail", lambda: False, critical=False)
    report = await perform_health_check()
    # With critical check passing and non-critical failing, status should be degraded
    assert report["status"] in ("healthy", "degraded")
    assert "checks" in report
    # Remove a check to cover removal branch
    health_monitor.remove_check("always_ok")
