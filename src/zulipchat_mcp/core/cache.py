"""Caching implementation for ZulipChat MCP Server."""

import difflib
import hashlib
import threading
import time
from typing import Any


class MessageCache:
    """Simple in-memory cache for messages."""

    def __init__(self, ttl: int = 300, max_entries: int = 1024) -> None:
        """Initialize cache.

        Args:
            ttl: Time to live in seconds (default: 5 minutes)
        """
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.cache: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl
        self.max_entries = max_entries
        self._lock = threading.RLock()

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """Create cache key from arguments."""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/not found
        """
        with self._lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.monotonic() - timestamp < self.ttl:
                    return value
                del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self.clear_expired()
            if key not in self.cache and len(self.cache) >= self.max_entries:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = (value, time.monotonic())

    def clear_expired(self) -> None:
        """Clear expired entries from cache."""
        with self._lock:
            now = time.monotonic()
            expired = [k for k, (_, t) in self.cache.items() if now - t >= self.ttl]
            for key in expired:
                del self.cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()

    def size(self) -> int:
        """Get number of cached items."""
        with self._lock:
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


class UserCache:
    """Cache for user information with fuzzy name resolution."""

    def __init__(self, ttl: int = 900) -> None:
        """Initialize user cache.

        Args:
            ttl: Time to live in seconds (default: 15 minutes)
        """
        self.cache = MessageCache(ttl)
        self._name_index: dict[str, str] = {}  # lowercase name → email
        self._email_to_delivery: dict[str, str] = {}
        self._ambiguous_names: set[str] = set()

    def get_users(self) -> list[Any] | None:
        """Get cached users list."""
        return self.cache.get("users_list")

    def set_users(self, users: list[Any]) -> None:
        """Cache users list and build name index."""
        self.cache.set("users_list", users)
        self._name_index.clear()
        self._email_to_delivery.clear()
        self._ambiguous_names.clear()
        for user in users:
            if not user.get("is_active", True):
                continue
            email = user.get("email", "")
            delivery = user.get("delivery_email", "")
            full_name = user.get("full_name", "").strip()
            # Map display email to delivery email for identity matching
            if email and delivery and email != delivery:
                self._email_to_delivery[email.lower()] = delivery.lower()
            if full_name and email:
                for name in {full_name.lower().strip(), full_name.split()[0].lower()}:
                    if name in self._ambiguous_names:
                        continue
                    if name in self._name_index and self._name_index[name] != email:
                        self._ambiguous_names.add(name)
                        del self._name_index[name]
                    else:
                        self._name_index[name] = email

    def resolve_user(self, query: str) -> dict[str, Any]:
        """Resolve a display name to email via fuzzy matching.

        Returns dict with email, full_name, matched, and confidence.
        """
        q = query.lower().strip()
        if self.get_users() is None or q in self._ambiguous_names:
            return {"email": None, "matched": None, "confidence": 0.0}

        # Exact match first
        if q in self._name_index:
            email = self._name_index[q]
            return {"email": email, "matched": q, "confidence": 1.0}

        # Fuzzy match
        matches = difflib.get_close_matches(q, self._name_index.keys(), n=1, cutoff=0.6)
        if matches:
            matched = matches[0]
            email = self._name_index[matched]
            score = difflib.SequenceMatcher(None, q, matched).ratio()
            return {"email": email, "matched": matched, "confidence": round(score, 2)}

        return {"email": None, "matched": None, "confidence": 0.0}


# Global cache instances
# LRU cache for frequently accessed data
