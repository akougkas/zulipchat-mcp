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
            patch("src.zulipchat_mcp.tools.event_management.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.event_management.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
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
    async def test_listen_events_with_callback(self, mock_deps):
        """Test listening for events with callback."""
        # Use a very short duration and patched sleep to make test fast
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_http,
        ):

            mock_post = AsyncMock()
            mock_http.return_value.__aenter__.return_value.post = mock_post

            # This runs the loop for 'duration' seconds (simulated by time.time)
            # We can't easily mock time.time in the loop condition without complex patching.
            # Instead, we rely on setting duration=0 or very small.
            # But the code `min(duration + 60, 600)` sets queue lifespan.
            # The loop condition is `while time.time() - start_time < duration`.
            # If we set duration=0.1, it should run once or twice.

            result = await listen_events(
                ["message"],
                duration=0.1,
                poll_interval=0.01,
                callback_url="http://callback.com",
            )

            assert result["status"] == "success"
            assert result["event_count"] > 0

            # Verify callback was called
            mock_post.assert_called()

            # Verify queue was deregistered at end
            mock_deps.deregister.assert_called()

    @pytest.mark.asyncio
    async def test_listen_events_timeout(self, mock_deps):
        """Test listen events stops after duration."""
        # Similar to above, verify it returns successfully after timeout
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await listen_events(["message"], duration=0.1, poll_interval=0.01)
            assert result["status"] == "success"
