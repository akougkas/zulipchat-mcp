"""Tests for async client and caching."""

import asyncio
import sys
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, "src")

from zulipchat_mcp.async_client import AsyncZulipClient
from zulipchat_mcp.cache import MessageCache, async_cache_decorator, cache_decorator
from zulipchat_mcp.config import ZulipConfig


class TestAsyncZulipClient:
    """Test async Zulip client."""

    @pytest.mark.asyncio
    async def test_async_client_context_manager(self):
        """Test async client context manager."""
        config = ZulipConfig(
            email="test@example.com",
            api_key="test_key",
            site="https://test.zulipchat.com",
        )

        async with AsyncZulipClient(config) as client:
            assert client.client is not None
            assert client.config == config

    @pytest.mark.asyncio
    async def test_send_message_async(self):
        """Test async message sending."""
        config = ZulipConfig(
            email="test@example.com",
            api_key="test_key",
            site="https://test.zulipchat.com",
        )

        client = AsyncZulipClient(config)

        # Mock the httpx client
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success", "id": 123}
        mock_response.raise_for_status = Mock()

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_client = Mock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_client

            result = await client.send_message_async(
                "stream", "general", "Test message", "test-topic"
            )

            assert result["result"] == "success"
            assert result["id"] == 123

    @pytest.mark.asyncio
    async def test_get_messages_async(self):
        """Test async message retrieval."""
        config = ZulipConfig(
            email="test@example.com",
            api_key="test_key",
            site="https://test.zulipchat.com",
        )

        client = AsyncZulipClient(config)

        # Mock the httpx client
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": "success",
            "messages": [
                {
                    "id": 1,
                    "sender_full_name": "John Doe",
                    "sender_email": "john@example.com",
                    "timestamp": 1640995200,
                    "content": "Test message",
                    "display_recipient": "general",
                    "subject": "test-topic",
                    "type": "stream",
                    "reactions": [],
                }
            ],
        }
        mock_response.raise_for_status = Mock()

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_client

            messages = await client.get_messages_async("general", limit=10)

            assert len(messages) == 1
            assert messages[0].id == 1
            assert messages[0].sender_full_name == "John Doe"


class TestCache:
    """Test caching functionality."""

    def test_message_cache_basic(self):
        """Test basic cache operations."""
        cache = MessageCache(ttl=1)

        # Test set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Test expiration
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_message_cache_clear_expired(self):
        """Test clearing expired entries."""
        cache = MessageCache(ttl=1)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert cache.size() == 2

        time.sleep(1.1)
        cache.clear_expired()
        assert cache.size() == 0

    def test_cache_decorator(self):
        """Test cache decorator."""
        call_count = 0

        @cache_decorator(ttl=1)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1

        # Different argument should execute function
        result3 = expensive_function(6)
        assert result3 == 12
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_cache_decorator(self):
        """Test async cache decorator."""
        call_count = 0

        @async_cache_decorator(ttl=1)
        async def async_expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x * 2

        # First call should execute function
        result1 = await async_expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = await async_expensive_function(5)
        assert result2 == 10
        assert call_count == 1


class TestCacheIntegration:
    """Test cache integration with client."""

    def test_stream_cache(self):
        """Test stream cache."""
        from zulipchat_mcp.cache import StreamCache

        cache = StreamCache(ttl=1)

        streams = [{"id": 1, "name": "general"}]
        cache.set_streams(streams)

        assert cache.get_streams() == streams

        # Test expiration
        time.sleep(1.1)
        assert cache.get_streams() is None

    def test_user_cache(self):
        """Test user cache."""
        from zulipchat_mcp.cache import UserCache

        cache = UserCache(ttl=1)

        users = [{"id": 1, "email": "test@example.com"}]
        cache.set_users(users)

        assert cache.get_users() == users

        # Test individual user caching
        user_info = {"id": 1, "name": "Test User"}
        cache.set_user_info("test@example.com", user_info)
        assert cache.get_user_info("test@example.com") == user_info
