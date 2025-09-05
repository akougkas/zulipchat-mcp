"""Caching implementation for ZulipChat MCP Server."""

import hashlib
import time
from collections.abc import Callable
from functools import lru_cache, wraps
from typing import Any


class MessageCache:
    """Simple in-memory cache for messages."""

    def __init__(self, ttl: int = 300) -> None:
        """Initialize cache.

        Args:
            ttl: Time to live in seconds (default: 5 minutes)
        """
        self.cache: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """Create cache key from arguments."""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/not found
        """
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = (value, time.time())

    def clear_expired(self) -> None:
        """Clear expired entries from cache."""
        now = time.time()
        expired = [k for k, (_, t) in self.cache.items() if now - t >= self.ttl]
        for key in expired:
            del self.cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

    def size(self) -> int:
        """Get number of cached items."""
        return len(self.cache)


class StreamCache:
    """Cache for stream information."""

    def __init__(self, ttl: int = 600) -> None:
        """Initialize stream cache.

        Args:
            ttl: Time to live in seconds (default: 10 minutes)
        """
        self.cache = MessageCache(ttl)

    def get_streams(self) -> list[Any] | None:
        """Get cached streams list."""
        return self.cache.get("streams_list")

    def set_streams(self, streams: list[Any]) -> None:
        """Cache streams list."""
        self.cache.set("streams_list", streams)

    def get_stream_info(self, stream_name: str) -> dict[str, Any] | None:
        """Get cached stream information."""
        return self.cache.get(f"stream_{stream_name}")

    def set_stream_info(self, stream_name: str, info: dict[str, Any]) -> None:
        """Cache stream information."""
        self.cache.set(f"stream_{stream_name}", info)


class UserCache:
    """Cache for user information."""

    def __init__(self, ttl: int = 900) -> None:
        """Initialize user cache.

        Args:
            ttl: Time to live in seconds (default: 15 minutes)
        """
        self.cache = MessageCache(ttl)

    def get_users(self) -> list[Any] | None:
        """Get cached users list."""
        return self.cache.get("users_list")

    def set_users(self, users: list[Any]) -> None:
        """Cache users list."""
        self.cache.set("users_list", users)

    def get_user_info(self, email: str) -> dict[str, Any] | None:
        """Get cached user information."""
        return self.cache.get(f"user_{email}")

    def set_user_info(self, email: str, info: dict[str, Any]) -> None:
        """Cache user information."""
        self.cache.set(f"user_{email}", info)


def cache_decorator(ttl: int = 300, key_prefix: str = "") -> Callable:
    """Decorator for caching function results.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys

    Returns:
        Decorated function with caching
    """
    cache = MessageCache(ttl)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = key_prefix + cache._make_key(*args, **kwargs)

            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        return wrapper

    return decorator


def async_cache_decorator(ttl: int = 300, key_prefix: str = "") -> Callable:
    """Decorator for caching async function results.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys

    Returns:
        Decorated async function with caching
    """
    cache = MessageCache(ttl)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = key_prefix + cache._make_key(*args, **kwargs)

            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Call async function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        return wrapper

    return decorator


# Global cache instances
message_cache = MessageCache(ttl=300)
stream_cache = StreamCache(ttl=600)
user_cache = UserCache(ttl=900)


# LRU cache for frequently accessed data
@lru_cache(maxsize=100)
def get_cached_stream_id(stream_name: str) -> int | None:
    """Get cached stream ID by name.

    Args:
        stream_name: Name of the stream

    Returns:
        Stream ID or None
    """
    # This would be populated by actual API calls
    return None


@lru_cache(maxsize=200)
def get_cached_user_id(email: str) -> int | None:
    """Get cached user ID by email.

    Args:
        email: User's email address

    Returns:
        User ID or None
    """
    # This would be populated by actual API calls
    return None
