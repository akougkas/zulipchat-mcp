"""Tests for core/cache.py."""

from unittest.mock import patch

import pytest

from src.zulipchat_mcp.core.cache import (
    MessageCache,
    StreamCache,
    UserCache,
)


class TestMessageCache:
    """Tests for MessageCache."""

    @pytest.fixture
    def cache(self):
        return MessageCache(ttl=60)

    def test_set_and_get(self, cache):
        """Test setting and getting a value."""
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_get_missing(self, cache):
        """Test getting a missing key."""
        assert cache.get("missing") is None

    def test_expiration(self, cache):
        """Test that values expire after TTL."""
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = 1000.0
            cache.set("key", "value")

            # Not expired
            mock_time.return_value = 1050.0
            assert cache.get("key") == "value"

            # Expired
            mock_time.return_value = 1061.0
            assert cache.get("key") is None

    def test_clear_expired(self, cache):
        """Test explicit clearing of expired items."""
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = 1000.0
            cache.set("valid", "v")
            cache.set("expired", "e")

            # Make one expired
            # We need to manually manipulate the cache dict or set with different times
            # But set() uses current time.time().

            # Strategy: Set both. Then advance time so one expires?
            # No, if we advance time, both expire if TTL same.

            # We can manually set timestamps in cache dict for testing.
            cache.cache["expired"] = ("e", 900.0)  # expired at 1000 (diff 100 > 60)
            cache.cache["valid"] = ("v", 990.0)  # valid at 1000 (diff 10 < 60)

            cache.clear_expired()

            assert "valid" in cache.cache
            assert "expired" not in cache.cache

    def test_clear(self, cache):
        """Test clearing all items."""
        cache.set("k", "v")
        cache.clear()
        assert cache.size() == 0

    def test_size(self, cache):
        """Test size method."""
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        assert cache.size() == 2


class TestStreamCache:
    """Tests for StreamCache."""

    @pytest.fixture
    def cache(self):
        return StreamCache(ttl=60)

    def test_streams_list(self, cache):
        """Test storing streams list."""
        streams = [{"name": "s1"}, {"name": "s2"}]
        cache.set_streams(streams)
        assert cache.get_streams() == streams


class TestUserCache:
    """Tests for UserCache."""

    @pytest.fixture
    def cache(self):
        return UserCache(ttl=60)

    def test_users_list(self, cache):
        """Test storing users list."""
        users = [{"email": "u1"}, {"email": "u2"}]
        cache.set_users(users)
        assert cache.get_users() == users


class TestCacheDecorators:
    """Tests for decorators."""
