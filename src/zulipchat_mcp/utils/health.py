"""Health check system for ZulipChat MCP Server."""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any

from ..config import ConfigManager
from ..core.cache import message_cache
from .metrics import metrics


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Individual health check."""

    def __init__(self, name: str, check_func: Any, critical: bool = True) -> None:
        """Initialize health check.

        Args:
            name: Name of the health check
            check_func: Function to execute for check
            critical: Whether this check is critical for overall health
        """
        self.name = name
        self.check_func = check_func
        self.critical = critical
        self.last_result: bool | None = None
        self.last_check_time: float | None = None
        self.last_error: str | None = None

    async def execute(self) -> bool:
        """Execute the health check.

        Returns:
            True if healthy, False otherwise
        """
        try:
            start_time = time.time()

            # Execute check (handle both sync and async functions)
            if asyncio.iscoroutinefunction(self.check_func):
                result = await self.check_func()
            else:
                result = self.check_func()

            self.last_result = bool(result)
            self.last_check_time = time.time() - start_time
            self.last_error = None

            return self.last_result

        except Exception as e:
            self.last_result = False
            self.last_check_time = 0
            self.last_error = str(e)
            return False

    def get_status(self) -> dict[str, Any]:
        """Get check status.

        Returns:
            Dictionary with check status information
        """
        return {
            "name": self.name,
            "healthy": self.last_result if self.last_result is not None else False,
            "status": "pass" if self.last_result else "fail",
            "critical": self.critical,
            "last_check_time_ms": (
                round(self.last_check_time * 1000, 2) if self.last_check_time else None
            ),
            "error": self.last_error,
        }


class HealthMonitor:
    """Health monitoring system."""

    def __init__(self) -> None:
        """Initialize health monitor."""
        self.checks: list[HealthCheck] = []
        self._setup_default_checks()

    def _setup_default_checks(self) -> None:
        """Set up default health checks."""
        # Config validation check
        self.add_check("config_validation", self._check_config, critical=True)

        # Cache operational check
        self.add_check("cache_operational", self._check_cache, critical=False)

        # Metrics collection check
        self.add_check("metrics_operational", self._check_metrics, critical=False)

    def _check_config(self) -> bool:
        """Check if configuration is valid.

        Returns:
            True if config is valid
        """
        try:
            config = ConfigManager()
            return config.validate_config()
        except Exception:
            return False

    def _check_cache(self) -> bool:
        """Check if cache is operational.

        Returns:
            True if cache is working
        """
        try:
            test_key = "_health_check_test"
            test_value = "test"
            message_cache.set(test_key, test_value)
            result = message_cache.get(test_key)
            return result == test_value
        except Exception:
            return False

    def _check_metrics(self) -> bool:
        """Check if metrics collection is working.

        Returns:
            True if metrics are being collected
        """
        try:
            metrics_data = metrics.get_metrics()
            return "uptime_seconds" in metrics_data
        except Exception:
            return False

    def add_check(self, name: str, check_func: Any, critical: bool = True) -> None:
        """Add a health check.

        Args:
            name: Name of the check
            check_func: Function to execute
            critical: Whether check is critical
        """
        self.checks.append(HealthCheck(name, check_func, critical))

    def remove_check(self, name: str) -> None:
        """Remove a health check.

        Args:
            name: Name of the check to remove
        """
        self.checks = [c for c in self.checks if c.name != name]

    async def check_health(self) -> dict[str, Any]:
        """Run all health checks.

        Returns:
            Health status report
        """
        start_time = time.time()

        # Execute all checks
        results = await asyncio.gather(
            *[check.execute() for check in self.checks], return_exceptions=True
        )

        # Process results
        checks_status = {}
        critical_healthy = True
        non_critical_healthy = True

        for check, result in zip(self.checks, results, strict=False):
            if isinstance(result, Exception):
                check.last_result = False
                check.last_error = str(result)

            status = check.get_status()
            checks_status[check.name] = status

            if not check.last_result:
                if check.critical:
                    critical_healthy = False
                else:
                    non_critical_healthy = False

        # Determine overall status
        if critical_healthy and non_critical_healthy:
            overall_status = HealthStatus.HEALTHY
        elif critical_healthy:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNHEALTHY

        # Get metrics snapshot
        metrics_snapshot = metrics.get_metrics()

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": round((time.time() - start_time) * 1000, 2),
            "checks": checks_status,
            "metrics": {
                "uptime_seconds": metrics_snapshot.get("uptime_seconds", 0),
                "total_requests": sum(metrics_snapshot.get("counters", {}).values()),
            },
            "version": "1.0.0",  # Should be imported from __init__.py
        }

    def get_liveness(self) -> dict[str, str]:
        """Get simple liveness check.

        Returns:
            Liveness status
        """
        return {"status": "alive", "timestamp": datetime.now().isoformat()}

    def get_readiness(self) -> dict[str, Any]:
        """Get readiness check (sync version).

        Returns:
            Readiness status
        """
        # Check only critical checks synchronously
        all_critical_healthy = True

        for check in self.checks:
            if check.critical:
                try:
                    # Simple synchronous check
                    if check.last_result is None:
                        # Never checked, assume not ready
                        all_critical_healthy = False
                        break
                    elif not check.last_result:
                        all_critical_healthy = False
                        break
                except Exception:
                    all_critical_healthy = False
                    break

        return {"ready": all_critical_healthy, "timestamp": datetime.now().isoformat()}


# Global health monitor instance
health_monitor = HealthMonitor()


async def perform_health_check() -> dict[str, Any]:
    """Perform a comprehensive health check.

    Returns:
        Health check results
    """
    return await health_monitor.check_health()


def get_liveness() -> dict[str, str]:
    """Get liveness status.

    Returns:
        Liveness check result
    """
    return health_monitor.get_liveness()


def get_readiness() -> dict[str, Any]:
    """Get readiness status.

    Returns:
        Readiness check result
    """
    return health_monitor.get_readiness()
