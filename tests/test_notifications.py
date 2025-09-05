"""Comprehensive tests for notifications module."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.zulipchat_mcp.config import ZulipConfig
from src.zulipchat_mcp.notifications import (
    NotificationPriority,
    SmartNotification,
    SmartNotificationSystem,
    smart_notify,
)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return ZulipConfig(
        email="test@example.com",
        api_key="test-api-key",
        site="https://test.zulipchat.com"
    )


class TestNotificationPriority:
    """Test notification priority enumeration."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.MEDIUM.value == "medium"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.URGENT.value == "urgent"


class TestSmartNotification:
    """Test SmartNotification model."""

    def test_smart_notification_creation(self):
        """Test creating a SmartNotification."""
        notification = SmartNotification(
            priority=NotificationPriority.HIGH,
            recipients=["user1@example.com", "user2@example.com"],
            content="Test notification"
        )

        assert notification.priority == NotificationPriority.HIGH
        assert notification.recipients == ["user1@example.com", "user2@example.com"]
        assert notification.content == "Test notification"
        assert notification.channels == ["zulip"]
        assert notification.retry_count == 0
        assert isinstance(notification.created_at, datetime)

    def test_smart_notification_with_custom_channels(self):
        """Test creating notification with custom channels."""
        notification = SmartNotification(
            priority=NotificationPriority.LOW,
            recipients=["user@example.com"],
            content="Test",
            channels=["zulip", "email", "slack"]
        )

        assert notification.channels == ["zulip", "email", "slack"]

    def test_smart_notification_with_retry_count(self):
        """Test creating notification with retry count."""
        notification = SmartNotification(
            priority=NotificationPriority.MEDIUM,
            recipients=["user@example.com"],
            content="Test",
            retry_count=3
        )

        assert notification.retry_count == 3


class TestSmartNotificationSystem:
    """Test SmartNotificationSystem functionality."""

    def test_initialization(self, sample_config):
        """Test notification system initialization."""
        system = SmartNotificationSystem(sample_config)

        assert system.config == sample_config

    @pytest.mark.asyncio
    async def test_notify_urgent(self, sample_config):
        """Test sending urgent notification."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"id": 123, "result": "success"}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await system.notify(
                recipients=["user1@example.com", "user2@example.com"],
                content="System down!",
                priority=NotificationPriority.URGENT
            )

            assert result["priority"] == "urgent"
            assert result["type"] == "urgent"
            assert len(result["results"]) == 2
            assert result["results"][0]["status"] == "sent"
            assert result["results"][1]["status"] == "sent"
            assert "timestamp" in result

            # Verify urgent notifications are sent as private messages
            assert mock_client.send_message_async.call_count == 2
            calls = mock_client.send_message_async.call_args_list

            # Check first call
            assert calls[0][1]["message_type"] == "private"
            assert calls[0][1]["to"] == "user1@example.com"
            assert "URGENT" in calls[0][1]["content"]
            assert "@**user1@example.com**" in calls[0][1]["content"]
            assert "@**user2@example.com**" in calls[0][1]["content"]

    @pytest.mark.asyncio
    async def test_notify_non_urgent(self, sample_config):
        """Test sending non-urgent notification."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"id": 456, "result": "success"}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await system.notify(
                recipients=["user@example.com"],
                content="Regular update",
                priority=NotificationPriority.MEDIUM
            )

            assert result["priority"] == "normal"
            assert result["type"] == "batch"
            assert len(result["results"]) == 1
            assert result["results"][0]["status"] == "sent"

            # Verify regular notifications
            mock_client.send_message_async.assert_called_once()
            call_args = mock_client.send_message_async.call_args[1]
            assert call_args["message_type"] == "private"
            assert call_args["content"] == "Regular update"
            assert "URGENT" not in call_args["content"]

    @pytest.mark.asyncio
    async def test_notify_with_failure(self, sample_config):
        """Test handling notification failures."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            # First call succeeds, second fails
            mock_client.send_message_async.side_effect = [
                {"id": 123, "result": "success"},
                Exception("Network error")
            ]
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await system.notify(
                recipients=["user1@example.com", "user2@example.com"],
                content="Test",
                priority=NotificationPriority.LOW
            )

            assert result["priority"] == "normal"
            assert len(result["results"]) == 2
            assert result["results"][0]["status"] == "sent"
            assert result["results"][1]["status"] == "failed"
            assert "Network error" in result["results"][1]["error"]

    @pytest.mark.asyncio
    async def test_send_urgent_notification_directly(self, sample_config):
        """Test _send_urgent_notification method directly."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"id": 789, "result": "success"}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await system._send_urgent_notification(
                recipients=["urgent@example.com"],
                content="Critical alert"
            )

            assert result["priority"] == "urgent"
            assert result["type"] == "urgent"
            assert len(result["results"]) == 1

            # Check the urgent message format
            call_args = mock_client.send_message_async.call_args[1]
            assert "🚨" in call_args["content"]
            assert "**URGENT**" in call_args["content"]
            assert "Critical alert" in call_args["content"]
            assert "@**urgent@example.com**" in call_args["content"]

    @pytest.mark.asyncio
    async def test_send_batch_notification_directly(self, sample_config):
        """Test _send_batch_notification method directly."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"id": 101, "result": "success"}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await system._send_batch_notification(
                recipients=["batch1@example.com", "batch2@example.com"],
                content="Batch message"
            )

            assert result["priority"] == "normal"
            assert result["type"] == "batch"
            assert len(result["results"]) == 2
            assert all(r["status"] == "sent" for r in result["results"])

            # Verify batch messages don't have urgent formatting
            calls = mock_client.send_message_async.call_args_list
            for call in calls:
                assert "URGENT" not in call[1]["content"]
                assert "🚨" not in call[1]["content"]

    @pytest.mark.asyncio
    async def test_notify_empty_recipients(self, sample_config):
        """Test sending notification with empty recipients list."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await system.notify(
                recipients=[],
                content="No recipients",
                priority=NotificationPriority.HIGH
            )

            assert result["results"] == []
            mock_client.send_message_async.assert_not_called()


class TestSmartNotifyFunction:
    """Test the smart_notify helper function."""

    @pytest.mark.asyncio
    async def test_smart_notify_default_priority(self, sample_config):
        """Test smart_notify with default priority."""
        with patch('src.zulipchat_mcp.notifications.SmartNotificationSystem') as mock_system_class:
            mock_system = AsyncMock()
            mock_system.notify.return_value = {"status": "sent"}
            mock_system_class.return_value = mock_system

            result = await smart_notify(
                config=sample_config,
                recipients=["user@example.com"],
                content="Test message"
            )

            assert result["status"] == "sent"
            mock_system.notify.assert_called_once_with(
                ["user@example.com"],
                "Test message",
                NotificationPriority.MEDIUM  # Default priority
            )

    @pytest.mark.asyncio
    async def test_smart_notify_with_priority(self, sample_config):
        """Test smart_notify with specified priority."""
        with patch('src.zulipchat_mcp.notifications.SmartNotificationSystem') as mock_system_class:
            mock_system = AsyncMock()
            mock_system.notify.return_value = {"status": "sent"}
            mock_system_class.return_value = mock_system

            result = await smart_notify(
                config=sample_config,
                recipients=["user@example.com"],
                content="Urgent message",
                priority=NotificationPriority.URGENT
            )

            assert result["status"] == "sent"
            mock_system.notify.assert_called_once_with(
                ["user@example.com"],
                "Urgent message",
                NotificationPriority.URGENT
            )


class TestIntegration:
    """Integration tests for notifications system."""

    @pytest.mark.asyncio
    async def test_full_notification_workflow(self, sample_config):
        """Test complete notification workflow with different priorities."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"id": 999, "result": "success"}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Test different priority levels
            priorities = [
                NotificationPriority.LOW,
                NotificationPriority.MEDIUM,
                NotificationPriority.HIGH,
                NotificationPriority.URGENT
            ]

            results = []
            for priority in priorities:
                result = await system.notify(
                    recipients=["test@example.com"],
                    content=f"{priority.value} priority message",
                    priority=priority
                )
                results.append(result)

            # Check that urgent messages get special treatment
            assert results[3]["priority"] == "urgent"
            assert results[3]["type"] == "urgent"

            # Check that non-urgent messages are batched
            for i in range(3):
                assert results[i]["priority"] == "normal"
                assert results[i]["type"] == "batch"

            # Verify message counts
            assert mock_client.send_message_async.call_count == 4

    @pytest.mark.asyncio
    async def test_error_recovery(self, sample_config):
        """Test error recovery in notification system."""
        system = SmartNotificationSystem(sample_config)

        with patch('src.zulipchat_mcp.notifications.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()

            # Simulate intermittent failures
            call_count = 0
            async def flaky_send(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 2 == 1:  # Fail on odd calls
                    raise Exception("Temporary failure")
                return {"id": call_count, "result": "success"}

            mock_client.send_message_async = flaky_send
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await system.notify(
                recipients=["user1@example.com", "user2@example.com", "user3@example.com"],
                content="Test",
                priority=NotificationPriority.MEDIUM
            )

            # Should have mix of successes and failures
            statuses = [r["status"] for r in result["results"]]
            assert "sent" in statuses
            assert "failed" in statuses

            # Verify error messages are captured
            failed_results = [r for r in result["results"] if r["status"] == "failed"]
            for failed in failed_results:
                assert "error" in failed
                assert "Temporary failure" in failed["error"]
