"""Comprehensive tests for health check system."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from zulipchat_mcp.health import (
    HealthCheck,
    HealthMonitor,
    HealthStatus,
    get_liveness,
    get_readiness,
    perform_health_check,
)


class TestHealthStatus:
    """Test health status enumeration."""

    def test_health_status_values(self):
        """Test health status enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestHealthCheck:
    """Test individual health check functionality."""

    def test_health_check_initialization(self):
        """Test health check initialization."""
        check_func = Mock()
        check = HealthCheck("test_check", check_func, critical=True)

        assert check.name == "test_check"
        assert check.check_func == check_func
        assert check.critical is True
        assert check.last_result is None
        assert check.last_check_time is None
        assert check.last_error is None

    @pytest.mark.asyncio
    async def test_health_check_execute_success_sync(self):
        """Test executing a successful synchronous health check."""
        check_func = Mock(return_value=True)
        check = HealthCheck("test_check", check_func)

        result = await check.execute()

        assert result is True
        assert check.last_result is True
        assert check.last_check_time is not None
        assert check.last_error is None
        check_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_execute_success_async(self):
        """Test executing a successful asynchronous health check."""

        async def async_check():
            return True

        check = HealthCheck("test_async", async_check)

        result = await check.execute()

        assert result is True
        assert check.last_result is True
        assert check.last_check_time is not None
        assert check.last_error is None

    @pytest.mark.asyncio
    async def test_health_check_execute_failure(self):
        """Test executing a failing health check."""
        check_func = Mock(return_value=False)
        check = HealthCheck("test_check", check_func)

        result = await check.execute()

        assert result is False
        assert check.last_result is False
        assert check.last_check_time is not None
        assert check.last_error is None

    @pytest.mark.asyncio
    async def test_health_check_execute_exception(self):
        """Test executing a health check that raises an exception."""
        check_func = Mock(side_effect=Exception("Test error"))
        check = HealthCheck("test_check", check_func)

        result = await check.execute()

        assert result is False
        assert check.last_result is False
        assert check.last_check_time is not None
        assert check.last_error == "Test error"


class TestHealthMonitor:
    """Test health monitor functionality."""

    def test_health_monitor_initialization(self):
        """Test health monitor initialization."""
        monitor = HealthMonitor()

        assert len(monitor.checks) > 0  # Should have default checks
        # Check for default checks
        check_names = [c.name for c in monitor.checks]
        assert "config_validation" in check_names
        assert "cache_operational" in check_names
        assert "metrics_operational" in check_names

    def test_add_check(self):
        """Test adding a new health check."""
        monitor = HealthMonitor()
        initial_count = len(monitor.checks)

        check_func = Mock(return_value=True)
        monitor.add_check("custom_check", check_func, critical=True)

        assert len(monitor.checks) == initial_count + 1
        check_names = [c.name for c in monitor.checks]
        assert "custom_check" in check_names

    def test_remove_check(self):
        """Test removing a health check."""
        monitor = HealthMonitor()

        # Add a check
        check_func = Mock(return_value=True)
        monitor.add_check("removable_check", check_func, critical=False)

        # Verify it was added
        check_names = [c.name for c in monitor.checks]
        assert "removable_check" in check_names

        # Remove it
        monitor.remove_check("removable_check")

        # Verify it was removed
        check_names = [c.name for c in monitor.checks]
        assert "removable_check" not in check_names

    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self):
        """Test health check when all checks pass."""
        monitor = HealthMonitor()

        # Replace checks with mocked ones
        monitor.checks = [
            HealthCheck("critical_check", Mock(return_value=True), critical=True),
            HealthCheck("non_critical_check", Mock(return_value=True), critical=False),
        ]

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {
                "uptime_seconds": 100,
                "counters": {"messages": 10},
            }

            result = await monitor.check_health()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "duration_ms" in result
        assert "checks" in result
        assert result["checks"]["critical_check"]["healthy"] is True
        assert result["checks"]["non_critical_check"]["healthy"] is True

    @pytest.mark.asyncio
    async def test_check_health_degraded(self):
        """Test health check when non-critical check fails."""
        monitor = HealthMonitor()

        # Set up mixed health checks
        monitor.checks = [
            HealthCheck("critical_check", Mock(return_value=True), critical=True),
            HealthCheck("non_critical_check", Mock(return_value=False), critical=False),
        ]

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {}

            result = await monitor.check_health()

        assert result["status"] == "degraded"
        assert result["checks"]["critical_check"]["healthy"] is True
        assert result["checks"]["non_critical_check"]["healthy"] is False

    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self):
        """Test health check when critical check fails."""
        monitor = HealthMonitor()

        # Set up failing critical check
        monitor.checks = [
            HealthCheck("critical_check", Mock(return_value=False), critical=True),
            HealthCheck("non_critical_check", Mock(return_value=True), critical=False),
        ]

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {}

            result = await monitor.check_health()

        assert result["status"] == "unhealthy"
        assert result["checks"]["critical_check"]["healthy"] is False

    @pytest.mark.asyncio
    async def test_check_health_with_exception(self):
        """Test health check when a check raises an exception."""
        monitor = HealthMonitor()

        # Set up check that raises exception
        monitor.checks = [
            HealthCheck(
                "error_check", Mock(side_effect=Exception("Test error")), critical=True
            ),
        ]

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {}

            result = await monitor.check_health()

        assert result["status"] == "unhealthy"
        assert result["checks"]["error_check"]["healthy"] is False
        assert result["checks"]["error_check"]["error"] == "Test error"

    def test_get_liveness(self):
        """Test liveness check."""
        monitor = HealthMonitor()

        result = monitor.get_liveness()

        assert result["status"] == "alive"
        assert "timestamp" in result

    def test_get_readiness_ready(self):
        """Test readiness check when ready."""
        monitor = HealthMonitor()

        # Set up checks with results
        critical_check = HealthCheck("critical", Mock(), critical=True)
        critical_check.last_result = True

        non_critical_check = HealthCheck("non_critical", Mock(), critical=False)
        non_critical_check.last_result = False  # Non-critical can fail

        monitor.checks = [critical_check, non_critical_check]

        result = monitor.get_readiness()

        assert result["ready"] is True
        assert "timestamp" in result

    def test_get_readiness_not_ready(self):
        """Test readiness check when not ready."""
        monitor = HealthMonitor()

        # Set up failing critical check
        critical_check = HealthCheck("critical", Mock(), critical=True)
        critical_check.last_result = False

        monitor.checks = [critical_check]

        result = monitor.get_readiness()

        assert result["ready"] is False
        assert "timestamp" in result

    def test_get_readiness_never_checked(self):
        """Test readiness when checks haven't been executed."""
        monitor = HealthMonitor()

        # Set up check that hasn't been executed
        critical_check = HealthCheck("critical", Mock(), critical=True)
        # last_result is None by default

        monitor.checks = [critical_check]

        result = monitor.get_readiness()

        assert result["ready"] is False  # Not ready if never checked


class TestDefaultHealthChecks:
    """Test the default health checks."""

    def test_check_config(self):
        """Test config validation check."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.ConfigManager") as mock_config_class:
            mock_config = Mock()
            mock_config.validate_config.return_value = True
            mock_config_class.return_value = mock_config

            result = monitor._check_config()

            assert result is True
            mock_config.validate_config.assert_called_once()

    def test_check_config_invalid(self):
        """Test config validation check with invalid config."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.ConfigManager") as mock_config_class:
            mock_config = Mock()
            mock_config.validate_config.return_value = False
            mock_config_class.return_value = mock_config

            result = monitor._check_config()

            assert result is False

    def test_check_config_exception(self):
        """Test config validation check with exception."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.ConfigManager") as mock_config_class:
            mock_config_class.side_effect = Exception("Config error")

            result = monitor._check_config()

            assert result is False

    def test_check_cache(self):
        """Test cache operational check."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.message_cache") as mock_cache:
            mock_cache.get.return_value = "test"
            mock_cache.set.return_value = None

            result = monitor._check_cache()

            assert result is True
            mock_cache.set.assert_called_once()
            mock_cache.get.assert_called_once()

    def test_check_cache_failure(self):
        """Test cache check when cache fails."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.message_cache") as mock_cache:
            mock_cache.get.return_value = "wrong_value"
            mock_cache.set.return_value = None

            result = monitor._check_cache()

            assert result is False

    def test_check_cache_exception(self):
        """Test cache check with exception."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.message_cache") as mock_cache:
            mock_cache.set.side_effect = Exception("Cache error")

            result = monitor._check_cache()

            assert result is False

    def test_check_metrics(self):
        """Test metrics operational check."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {"uptime_seconds": 100}

            result = monitor._check_metrics()

            assert result is True
            mock_metrics.get_metrics.assert_called_once()

    def test_check_metrics_missing_data(self):
        """Test metrics check with missing data."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {}

            result = monitor._check_metrics()

            assert result is False

    def test_check_metrics_exception(self):
        """Test metrics check with exception."""
        monitor = HealthMonitor()

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.side_effect = Exception("Metrics error")

            result = monitor._check_metrics()

            assert result is False


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_perform_health_check(self):
        """Test the perform_health_check function."""
        with patch("zulipchat_mcp.health.health_monitor") as mock_monitor:
            mock_monitor.check_health = AsyncMock(return_value={"status": "healthy"})

            result = await perform_health_check()

            assert result["status"] == "healthy"
            mock_monitor.check_health.assert_called_once()

    def test_get_liveness_function(self):
        """Test the get_liveness function."""
        with patch("zulipchat_mcp.health.health_monitor") as mock_monitor:
            mock_monitor.get_liveness.return_value = {"status": "alive"}

            result = get_liveness()

            assert result["status"] == "alive"
            mock_monitor.get_liveness.assert_called_once()

    def test_get_readiness_function(self):
        """Test the get_readiness function."""
        with patch("zulipchat_mcp.health.health_monitor") as mock_monitor:
            mock_monitor.get_readiness.return_value = {"ready": True}

            result = get_readiness()

            assert result["ready"] is True
            mock_monitor.get_readiness.assert_called_once()


class TestIntegration:
    """Integration tests for health system."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        """Test running multiple health checks concurrently."""
        monitor = HealthMonitor()

        # Create slow async checks
        async def slow_check():
            await asyncio.sleep(0.1)
            return True

        # Add multiple slow checks
        for i in range(5):
            monitor.add_check(f"slow_check_{i}", slow_check, critical=False)

        with patch("zulipchat_mcp.health.metrics") as mock_metrics:
            mock_metrics.get_metrics.return_value = {}

            start_time = time.time()
            result = await monitor.check_health()
            elapsed_time = time.time() - start_time

        # Should run concurrently, so total time should be close to 0.1s, not 0.5s
        assert elapsed_time < 0.3  # Allow some overhead
        assert "slow_check_0" in result["checks"]
        assert "slow_check_4" in result["checks"]

    @pytest.mark.asyncio
    async def test_health_system_integration(self):
        """Test complete health system integration."""
        monitor = HealthMonitor()

        # Register custom check
        custom_check_called = False

        def custom_check():
            nonlocal custom_check_called
            custom_check_called = True
            return True

        monitor.add_check("custom", custom_check, critical=False)

        # Mock external dependencies
        with patch("zulipchat_mcp.health.ConfigManager") as mock_config_class:
            mock_config = Mock()
            mock_config.validate_config.return_value = True
            mock_config_class.return_value = mock_config

            with patch("zulipchat_mcp.health.message_cache") as mock_cache:
                mock_cache.get.return_value = "test"
                mock_cache.set.return_value = None

                with patch("zulipchat_mcp.health.metrics") as mock_metrics:
                    mock_metrics.get_metrics.return_value = {"uptime_seconds": 100}

                    # Run health checks
                    result = await monitor.check_health()

                    # Verify results
                    assert result["status"] in ["healthy", "degraded", "unhealthy"]
                    assert "custom" in result["checks"]
                    assert custom_check_called

                    # Test liveness
                    liveness = monitor.get_liveness()
                    assert liveness["status"] == "alive"

                    # Test readiness
                    readiness = monitor.get_readiness()
                    assert "ready" in readiness
