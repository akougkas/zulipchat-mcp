"""Tests for write operations in tools/schedule_messaging.py."""

import pytest
import time
from unittest.mock import MagicMock, patch
from src.zulipchat_mcp.tools.schedule_messaging import (
    create_scheduled_message,
    update_scheduled_message,
    delete_scheduled_message
)

class TestScheduledMessages:
    """Tests for scheduled message operations."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {
            "result": "success",
            "scheduled_message_id": 999
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with patch("src.zulipchat_mcp.tools.schedule_messaging.ConfigManager"), \
             patch("src.zulipchat_mcp.tools.schedule_messaging.ZulipClientWrapper") as mock_wrapper:
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_schedule_future_message(self, mock_deps):
        """Test scheduling a message for the future."""
        future_ts = int(time.time()) + 3600
        result = await create_scheduled_message(
            type="stream",
            to=123,
            content="Future me",
            scheduled_delivery_timestamp=future_ts,
            topic="planning"
        )
        assert result["status"] == "success"
        assert result["scheduled_message_id"] == 999
        
        mock_deps.client.call_endpoint.assert_called()
        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["scheduled_delivery_timestamp"] == future_ts
        assert request["type"] == "stream"

    @pytest.mark.asyncio
    async def test_schedule_past_timestamp_fails(self, mock_deps):
        """Test scheduling for past time (backend rejection)."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Scheduled delivery time must be in the future."
        }
        past_ts = int(time.time()) - 3600
        result = await create_scheduled_message(
            type="stream",
            to=123,
            content="Time travel",
            scheduled_delivery_timestamp=past_ts,
            topic="history"
        )
        assert result["status"] == "error"
        assert "must be in the future" in result["error"]

    @pytest.mark.asyncio
    async def test_schedule_invalid_timestamp(self, mock_deps):
        """Test scheduling with invalid input (e.g. topic missing for stream)."""
        result = await create_scheduled_message(
            type="stream",
            to=123,
            content="No topic",
            scheduled_delivery_timestamp=int(time.time()) + 100
        )
        assert result["status"] == "error"
        assert "Topic required" in result["error"]

    @pytest.mark.asyncio
    async def test_update_scheduled_time(self, mock_deps):
        """Test updating a scheduled message time."""
        new_ts = int(time.time()) + 7200
        result = await update_scheduled_message(
            scheduled_message_id=999,
            scheduled_delivery_timestamp=new_ts
        )
        assert result["status"] == "success"
        assert "scheduled_delivery_timestamp" in result["updated_fields"]

    @pytest.mark.asyncio
    async def test_update_nonexistent_scheduled(self, mock_deps):
        """Test updating nonexistent message."""
        mock_deps.client.call_endpoint.return_value = {"result": "error", "msg": "Scheduled message does not exist"}
        result = await update_scheduled_message(888, content="New content")
        assert result["status"] == "error"
        assert "does not exist" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_scheduled_message(self, mock_deps):
        """Test deleting scheduled message."""
        result = await delete_scheduled_message(999)
        assert result["status"] == "success"
        assert result["action"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_already_sent(self, mock_deps):
        """Test deleting message that was already sent or doesn't exist."""
        mock_deps.client.call_endpoint.return_value = {"result": "error", "msg": "Scheduled message does not exist"}
        result = await delete_scheduled_message(999)
        assert result["status"] == "error"

