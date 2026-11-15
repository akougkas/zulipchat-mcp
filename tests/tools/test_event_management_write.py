"""Tests for write operations in tools/event_management.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.event_management import (
    deregister_events,
    get_events,
    listen_events,
    register_events,
)


class TestEventManagement:
    """Tests for event management operations."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.register.return_value = {
            "result": "success",
            "queue_id": "queue-1",
            "last_event_id": 100,
        }
        client.get_events.return_value = {
            "result": "success",
            "events": [{"id": 101, "type": "message"}],
        }
        client.deregister.return_value = {"result": "success"}
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch(
                "src.zulipchat_mcp.tools.event_management.get_client"
            ) as mock_get_client,
        ):
            mock_get_client.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_register_events_success(self, mock_deps):
        """Test registering for events."""
        result = await register_events(["message"])
        assert result["status"] == "success"
        assert result["queue_id"] == "queue-1"

        mock_deps.register.assert_called()

    @pytest.mark.asyncio
    async def test_register_invalid_event_type(self, mock_deps):
        """Test registration with invalid event type (backend error)."""
        mock_deps.register.return_value = {
            "result": "error",
            "msg": "Invalid event type",
        }
        result = await register_events(["bad_type"])
        assert result["status"] == "error"
        assert "Invalid event type" in result["error"]

    @pytest.mark.asyncio
    async def test_get_events_valid_queue(self, mock_deps):
        """Test getting events from valid queue."""
        result = await get_events("queue-1", 100)
        assert result["status"] == "success"
        assert len(result["events"]) == 1

        mock_deps.get_events.assert_called_with(
            queue_id="queue-1",
            last_event_id=100,
            dont_block=False,
            timeout=10,
            apply_markdown=True,
            client_gravatar=False,
        )

    @pytest.mark.asyncio
    async def test_get_events_expired_queue(self, mock_deps):
        """Test getting events from expired queue."""
        mock_deps.get_events.return_value = {
            "result": "error",
            "msg": "Bad event queue id",
        }
        result = await get_events("queue-old", 100)
        assert result["status"] == "error"
        assert "Bad event queue id" in result["error"]

    @pytest.mark.asyncio
    async def test_deregister_events(self, mock_deps):
        """Test deregistering queue."""
        result = await deregister_events("queue-1")
        assert result["status"] == "success"
        mock_deps.deregister.assert_called_with("queue-1")

    @pytest.mark.asyncio
    async def test_deregister_nonexistent_queue(self, mock_deps):
        """Test deregistering nonexistent queue."""
        mock_deps.deregister.return_value = {
            "result": "error",
            "msg": "Bad event queue id",
        }
        result = await deregister_events("queue-bad")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_listen_events_returns_events_and_sends_them_nowhere(self, mock_deps):
        """Events reach the caller only; there is no webhook to another host."""
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_http,
        ):
            with pytest.raises(TypeError, match="callback_url"):
                await listen_events(["message"], callback_url="http://callback.com")

            # The loop runs while time.time() - start_time < duration.
            result = await listen_events(["message"], duration=0.1, poll_interval=0.01)

            assert result["status"] == "success"
            assert result["event_count"] > 0
            mock_http.assert_not_called()

            # Verify queue was deregistered at end
            mock_deps.deregister.assert_called()

    @pytest.mark.asyncio
    async def test_listen_events_timeout(self, mock_deps):
        """Test listen events stops after duration."""
        # Similar to above, verify it returns successfully after timeout
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await listen_events(["message"], duration=0.1, poll_interval=0.01)
            assert result["status"] == "success"
