"""Comprehensive tests for the native Zulip scheduler.

The scheduler.py module provides a complete message scheduling system using
Zulip's native scheduled messages API with 433 lines of functionality.

Key components tested:
- ScheduledMessage data model with Pydantic validation
- MessageScheduler with async HTTP client for Zulip API
- Context manager support for async operations
- Single message scheduling and cancellation
- Recurring message scheduling with intervals
- Daily standup automation with weekday filtering
- Bulk scheduling operations
- Time range filtering
- Convenience functions for common operations

This aims for 80%+ coverage of the scheduler functionality.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from zulipchat_mcp.config import ZulipConfig
from zulipchat_mcp.scheduler import (
    MessageScheduler,
    ScheduledMessage,
    cancel_scheduled_message,
    schedule_message,
    schedule_reminder,
)


@pytest.fixture
def sample_config():
    """Sample Zulip configuration."""
    return ZulipConfig(
        email="test@example.com",
        api_key="test-api-key",
        site="https://test.zulipchat.com",
    )


@pytest.fixture
def sample_scheduled_message():
    """Sample scheduled message."""
    return ScheduledMessage(
        content="Test scheduled message",
        scheduled_time=datetime.now() + timedelta(hours=1),
        message_type="stream",
        recipients="general",
        topic="test-topic",
        scheduled_id=None,
    )


class TestScheduledMessage:
    """Test the ScheduledMessage data model."""

    def test_scheduled_message_initialization(self):
        """Test ScheduledMessage initialization with required fields."""
        scheduled_time = datetime.now() + timedelta(hours=2)

        message = ScheduledMessage(
            content="Hello world!",
            scheduled_time=scheduled_time,
            message_type="stream",
            recipients="general",
            topic="announcements",
            scheduled_id=None,
        )

        assert message.content == "Hello world!"
        assert message.scheduled_time == scheduled_time
        assert message.message_type == "stream"
        assert message.recipients == "general"
        assert message.topic == "announcements"
        assert message.scheduled_id is None

    def test_scheduled_message_private_message(self):
        """Test ScheduledMessage for private messages."""
        message = ScheduledMessage(
            content="Private message",
            scheduled_time=datetime.now() + timedelta(minutes=30),
            message_type="private",
            recipients=["user1@example.com", "user2@example.com"],
            topic=None,
            scheduled_id=None,
        )

        assert message.message_type == "private"
        assert message.recipients == ["user1@example.com", "user2@example.com"]
        assert message.topic is None

    def test_scheduled_message_with_scheduled_id(self):
        """Test ScheduledMessage with scheduled_id set."""
        message = ScheduledMessage(
            content="Message with ID",
            scheduled_time=datetime.now() + timedelta(days=1),
            message_type="stream",
            recipients="general",
            topic="test",
            scheduled_id=12345,
        )

        assert message.scheduled_id == 12345


class TestMessageScheduler:
    """Test the MessageScheduler core functionality."""

    def test_scheduler_initialization(self, sample_config):
        """Test MessageScheduler initialization."""
        scheduler = MessageScheduler(sample_config)

        assert scheduler.config == sample_config
        assert scheduler.base_url == "https://test.zulipchat.com/api/v1"
        assert scheduler.auth == ("test@example.com", "test-api-key")
        assert scheduler.client is None

    def test_datetime_timestamp_conversion(self, sample_config):
        """Test datetime to timestamp conversion utilities."""
        scheduler = MessageScheduler(sample_config)

        # Test datetime to timestamp
        dt = datetime(2024, 1, 15, 12, 30, 0)
        timestamp = scheduler._datetime_to_timestamp(dt)
        assert isinstance(timestamp, int)
        assert timestamp == int(dt.timestamp())

        # Test timestamp to datetime
        converted_dt = scheduler._timestamp_to_datetime(timestamp)
        assert converted_dt == dt

    @pytest.mark.asyncio
    async def test_context_manager_functionality(self, sample_config):
        """Test async context manager support."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            async with MessageScheduler(sample_config) as scheduler:
                assert scheduler.client is mock_client

            # Client should be closed after exiting context
            mock_client.aclose.assert_called_once()

    def test_ensure_client_creates_client(self, sample_config):
        """Test that _ensure_client creates client when needed."""
        scheduler = MessageScheduler(sample_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = scheduler._ensure_client()

            assert client is mock_client
            assert scheduler.client is mock_client
            mock_client_class.assert_called_once_with(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                auth=("test@example.com", "test-api-key"),
            )


class TestScheduleMessage:
    """Test message scheduling functionality."""

    @pytest.mark.asyncio
    async def test_schedule_stream_message_success(
        self, sample_config, sample_scheduled_message
    ):
        """Test successful stream message scheduling."""
        scheduler = MessageScheduler(sample_config)

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": "success",
            "scheduled_message_id": 12345,
        }
        mock_response.raise_for_status = Mock()

        # Mock client
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            result = await scheduler.schedule_message(sample_scheduled_message)

        # Verify API call
        expected_timestamp = int(sample_scheduled_message.scheduled_time.timestamp())
        mock_client.post.assert_called_once_with(
            f"{scheduler.base_url}/scheduled_messages",
            data={
                "content": "Test scheduled message",
                "scheduled_delivery_timestamp": expected_timestamp,
                "type": "stream",
                "to": "general",
                "topic": "test-topic",
            },
        )

        # Verify result
        assert result["result"] == "success"
        assert result["scheduled_message_id"] == 12345
        assert sample_scheduled_message.scheduled_id == 12345

    @pytest.mark.asyncio
    async def test_schedule_private_message_success(self, sample_config):
        """Test scheduling private message."""
        scheduler = MessageScheduler(sample_config)

        private_message = ScheduledMessage(
            content="Private scheduled message",
            scheduled_time=datetime.now() + timedelta(hours=1),
            message_type="private",
            recipients=["user@example.com"],
            topic=None,
            scheduled_id=None,
        )

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": "success",
            "scheduled_message_id": 67890,
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            await scheduler.schedule_message(private_message)

        # Verify private message formatting
        call_args = mock_client.post.call_args[1]["data"]
        assert call_args["type"] == "private"
        assert call_args["to"] == json.dumps(["user@example.com"])
        assert "topic" not in call_args

    @pytest.mark.asyncio
    async def test_schedule_message_api_error(
        self, sample_config, sample_scheduled_message
    ):
        """Test handling API errors during scheduling."""
        scheduler = MessageScheduler(sample_config)

        # Mock HTTP error
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "API Error", request=Mock(), response=Mock()
        )

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await scheduler.schedule_message(sample_scheduled_message)


class TestCancelScheduled:
    """Test scheduled message cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_scheduled_success(self, sample_config):
        """Test successful message cancellation."""
        scheduler = MessageScheduler(sample_config)

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            result = await scheduler.cancel_scheduled(12345)

        mock_client.delete.assert_called_once_with(
            f"{scheduler.base_url}/scheduled_messages/12345"
        )
        assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_cancel_scheduled_not_found(self, sample_config):
        """Test cancelling non-existent scheduled message."""
        scheduler = MessageScheduler(sample_config)

        mock_client = AsyncMock()
        mock_client.delete.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=Mock()
        )

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await scheduler.cancel_scheduled(99999)


class TestListScheduled:
    """Test listing scheduled messages."""

    @pytest.mark.asyncio
    async def test_list_scheduled_success(self, sample_config):
        """Test successful listing of scheduled messages."""
        scheduler = MessageScheduler(sample_config)

        # Mock API response
        scheduled_messages = [
            {"scheduled_message_id": 1, "content": "Message 1"},
            {"scheduled_message_id": 2, "content": "Message 2"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = {
            "result": "success",
            "scheduled_messages": scheduled_messages,
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            result = await scheduler.list_scheduled()

        mock_client.get.assert_called_once_with(
            f"{scheduler.base_url}/scheduled_messages"
        )
        assert result == scheduled_messages

    @pytest.mark.asyncio
    async def test_list_scheduled_empty_response(self, sample_config):
        """Test listing when no scheduled messages exist."""
        scheduler = MessageScheduler(sample_config)

        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            result = await scheduler.list_scheduled()

        assert result == []


class TestUpdateScheduled:
    """Test updating scheduled message times."""

    @pytest.mark.asyncio
    async def test_update_scheduled_success(self, sample_config):
        """Test successful scheduled message time update."""
        scheduler = MessageScheduler(sample_config)

        new_time = datetime.now() + timedelta(hours=2)

        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.patch.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            result = await scheduler.update_scheduled(12345, new_time)

        mock_client.patch.assert_called_once_with(
            f"{scheduler.base_url}/scheduled_messages/12345",
            data={"scheduled_delivery_timestamp": int(new_time.timestamp())},
        )
        assert result["result"] == "success"


class TestRecurringMessages:
    """Test recurring message scheduling."""

    @pytest.mark.asyncio
    async def test_schedule_recurring_success(self, sample_config):
        """Test scheduling recurring messages."""
        scheduler = MessageScheduler(sample_config)

        base_message = ScheduledMessage(
            content="Daily reminder",
            scheduled_time=datetime.now() + timedelta(hours=1),
            message_type="stream",
            recipients="general",
            topic="reminders",
            scheduled_id=None,
        )

        # Mock successful responses
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": "success",
            "scheduled_message_id": 123,
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            results = await scheduler.schedule_recurring(
                base_message, interval=timedelta(days=1), count=3
            )

        # Should have scheduled 3 messages
        assert len(results) == 3
        assert mock_client.post.call_count == 3

        # Each result should be successful
        for result in results:
            assert result["result"] == "success"


class TestReminders:
    """Test reminder scheduling functionality."""

    @pytest.mark.asyncio
    async def test_schedule_reminder_success(self, sample_config):
        """Test scheduling a reminder message."""
        scheduler = MessageScheduler(sample_config)

        mock_response = Mock()
        mock_response.json.return_value = {
            "result": "success",
            "scheduled_message_id": 456,
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(scheduler, "_ensure_client", return_value=mock_client):
            result = await scheduler.schedule_reminder(
                content="Meeting in 30 minutes",
                minutes_from_now=25,
                recipients="user@example.com",
                message_type="private",
            )

        # Verify the reminder was formatted correctly
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["content"] == "⏰ Reminder: Meeting in 30 minutes"
        assert call_data["type"] == "private"
        assert call_data["to"] == json.dumps(["user@example.com"])

        assert result["result"] == "success"


class TestDailyStandup:
    """Test daily standup scheduling functionality."""

    @pytest.mark.asyncio
    async def test_schedule_daily_standup_success(self, sample_config):
        """Test scheduling daily standup messages."""
        scheduler = MessageScheduler(sample_config)

        mock_response = Mock()
        mock_response.json.return_value = {
            "result": "success",
            "scheduled_message_id": 789,
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        # Mock datetime.now() to control the scheduling
        with patch("zulipchat_mcp.scheduler.datetime") as mock_datetime:
            # Set a specific Monday
            mock_datetime.now.return_value = datetime(2024, 1, 15, 8, 0, 0)  # Monday
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            with patch.object(scheduler, "_ensure_client", return_value=mock_client):
                results = await scheduler.schedule_daily_standup(
                    stream="team",
                    topic="Daily Standup",
                    time_of_day="09:00",
                    days_ahead=7,
                )

        # Should schedule for weekdays only (skip weekends)
        assert len(results) == 5  # 5 weekdays in a week

        # Each result should be successful
        for result in results:
            assert result["result"] == "success"

        # Verify standup content
        first_call_data = mock_client.post.call_args_list[0][1]["data"]
        assert "Daily Standup" in first_call_data["content"]
        assert "@**all**" in first_call_data["content"]
        assert first_call_data["to"] == "team"
        assert first_call_data["topic"] == "Daily Standup"

    @pytest.mark.asyncio
    async def test_schedule_daily_standup_invalid_time_format(self, sample_config):
        """Test daily standup with invalid time format."""
        scheduler = MessageScheduler(sample_config)

        with pytest.raises(ValueError, match="time_of_day must be in HH:MM format"):
            await scheduler.schedule_daily_standup(
                stream="team", topic="standup", time_of_day="invalid-time"
            )


class TestBulkOperations:
    """Test bulk scheduling operations."""

    @pytest.mark.asyncio
    async def test_bulk_schedule_success(self, sample_config):
        """Test bulk scheduling multiple messages."""
        scheduler = MessageScheduler(sample_config)

        messages = [
            ScheduledMessage(
                content=f"Message {i}",
                scheduled_time=datetime.now() + timedelta(hours=i),
                message_type="stream",
                recipients="general",
                topic="bulk",
                scheduled_id=None,
            )
            for i in range(1, 4)
        ]

        # Mock successful responses
        mock_results = [
            {"result": "success", "scheduled_message_id": i} for i in range(100, 103)
        ]

        with patch.object(scheduler, "schedule_message") as mock_schedule:
            mock_schedule.side_effect = mock_results

            results = await scheduler.bulk_schedule(messages)

        assert len(results) == 3
        assert mock_schedule.call_count == 3

        for i, result in enumerate(results):
            assert result["result"] == "success"
            assert result["scheduled_message_id"] == 100 + i


class TestTimeRangeFiltering:
    """Test time range filtering functionality."""

    @pytest.mark.asyncio
    async def test_get_scheduled_by_time_range(self, sample_config):
        """Test filtering scheduled messages by time range."""
        scheduler = MessageScheduler(sample_config)

        # Mock scheduled messages with different times
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        all_scheduled = [
            {
                "scheduled_message_id": 1,
                "scheduled_delivery_timestamp": int(base_time.timestamp()),
            },
            {
                "scheduled_message_id": 2,
                "scheduled_delivery_timestamp": int(
                    (base_time + timedelta(hours=2)).timestamp()
                ),
            },
            {
                "scheduled_message_id": 3,
                "scheduled_delivery_timestamp": int(
                    (base_time + timedelta(hours=5)).timestamp()
                ),
            },
        ]

        with patch.object(scheduler, "list_scheduled", return_value=all_scheduled):
            # Filter for messages in first 3 hours
            results = await scheduler.get_scheduled_by_time_range(
                start_time=base_time, end_time=base_time + timedelta(hours=3)
            )

        # Should return first 2 messages only
        assert len(results) == 2
        assert results[0]["scheduled_message_id"] == 1
        assert results[1]["scheduled_message_id"] == 2


class TestCancelAll:
    """Test cancelling all scheduled messages."""

    @pytest.mark.asyncio
    async def test_cancel_all_scheduled_success(self, sample_config):
        """Test cancelling all scheduled messages."""
        scheduler = MessageScheduler(sample_config)

        # Mock existing scheduled messages
        scheduled_messages = [
            {"scheduled_message_id": 1},
            {"scheduled_message_id": 2},
            {"scheduled_message_id": 3},
        ]

        with patch.object(scheduler, "list_scheduled", return_value=scheduled_messages):
            with patch.object(scheduler, "cancel_scheduled") as mock_cancel:
                mock_cancel.return_value = {"result": "success"}

                results = await scheduler.cancel_all_scheduled()

        # Should have cancelled all 3 messages
        assert len(results) == 3
        assert mock_cancel.call_count == 3

        # Verify the correct IDs were cancelled
        cancelled_ids = [call[0][0] for call in mock_cancel.call_args_list]
        assert cancelled_ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_cancel_all_scheduled_no_messages(self, sample_config):
        """Test cancelling all when no messages exist."""
        scheduler = MessageScheduler(sample_config)

        with patch.object(scheduler, "list_scheduled", return_value=[]):
            results = await scheduler.cancel_all_scheduled()

        assert results == []


class TestConvenienceFunctions:
    """Test convenience functions for common operations."""

    @pytest.mark.asyncio
    async def test_schedule_message_convenience_function(
        self, sample_config, sample_scheduled_message
    ):
        """Test the convenience function for scheduling messages."""
        with patch(
            "src.zulipchat_mcp.scheduler.MessageScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_message.return_value = {"result": "success"}
            # Configure the async context manager properly
            mock_scheduler.__aenter__.return_value = mock_scheduler
            mock_scheduler.__aexit__.return_value = None
            mock_scheduler_class.return_value = mock_scheduler

            result = await schedule_message(sample_config, sample_scheduled_message)

            # Verify context manager was used
            mock_scheduler.__aenter__.assert_called_once()
            mock_scheduler.__aexit__.assert_called_once()
            mock_scheduler.schedule_message.assert_called_once_with(
                sample_scheduled_message
            )
            assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_schedule_reminder_convenience_function(self, sample_config):
        """Test the convenience function for scheduling reminders."""
        with patch(
            "src.zulipchat_mcp.scheduler.MessageScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_reminder.return_value = {"result": "success"}
            # Configure the async context manager properly
            mock_scheduler.__aenter__.return_value = mock_scheduler
            mock_scheduler.__aexit__.return_value = None
            mock_scheduler_class.return_value = mock_scheduler

            result = await schedule_reminder(
                config=sample_config,
                content="Test reminder",
                minutes_from_now=30,
                recipients=["user@example.com"],
                message_type="private",
            )

            mock_scheduler.schedule_reminder.assert_called_once_with(
                "Test reminder", 30, ["user@example.com"], "private", None
            )
            assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_cancel_scheduled_message_convenience_function(self, sample_config):
        """Test the convenience function for cancelling scheduled messages."""
        with patch(
            "src.zulipchat_mcp.scheduler.MessageScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = AsyncMock()
            mock_scheduler.cancel_scheduled.return_value = {"result": "success"}
            # Configure the async context manager properly
            mock_scheduler.__aenter__.return_value = mock_scheduler
            mock_scheduler.__aexit__.return_value = None
            mock_scheduler_class.return_value = mock_scheduler

            result = await cancel_scheduled_message(sample_config, 12345)

            mock_scheduler.cancel_scheduled.assert_called_once_with(12345)
            assert result["result"] == "success"


class TestAsyncCleanup:
    """Test async resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_method(self, sample_config):
        """Test explicit close method."""
        scheduler = MessageScheduler(sample_config)

        mock_client = AsyncMock()
        scheduler.client = mock_client

        await scheduler.close()

        mock_client.aclose.assert_called_once()
        assert scheduler.client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self, sample_config):
        """Test close when no client exists."""
        scheduler = MessageScheduler(sample_config)

        # Should not raise exception when client is None
        await scheduler.close()
        assert scheduler.client is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
