"""Tests for utils.health to raise coverage."""

from __future__ import annotations

import asyncio

from zulipchat_mcp.utils.health import (
    HealthCheck,
    HealthMonitor,
    perform_health_check,
    get_liveness,
    get_readiness,
)


def test_healthcheck_sync_and_status() -> None:
    hc = HealthCheck("ok", lambda: True)
    assert asyncio.get_event_loop().run_until_complete(hc.execute()) is True
    st = hc.get_status()
    assert st["name"] == "ok" and st["healthy"] is True and st["status"] == "pass"


def test_health_monitor_add_remove_and_readiness() -> None:
    hm = HealthMonitor()
    # Replace default checks with a deterministic one
    hm.checks = []
    hm.add_check("always", lambda: True, critical=True)
    # Readiness false before execute
    ready0 = hm.get_readiness()["ready"]
    assert ready0 is False
    # Execute to set last_result
    asyncio.get_event_loop().run_until_complete(hm.check_health())
    # Now readiness is true
    assert hm.get_readiness()["ready"] is True
    # Remove and verify
    hm.remove_check("always")
    assert all(c.name != "always" for c in hm.checks)


def test_perform_health_check_and_liveness() -> None:
    # Smoke: functions return dicts
    l = get_liveness()
    assert l["status"] == "alive"
    r = get_readiness()
    assert "ready" in r
    full = asyncio.get_event_loop().run_until_complete(perform_health_check())
    assert full["status"] in ("healthy", "degraded", "unhealthy")

