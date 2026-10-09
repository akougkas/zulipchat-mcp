"""Bounded, identity-scoped read snapshots with duplicate-request coalescing."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cache import MessageCache

_root: Path | None = None
_instances: weakref.WeakSet[ReadSnapshots] = weakref.WeakSet()
_instances_lock = threading.Lock()


def configure_snapshot_root(root: Path | None) -> None:
    """Set the account-bound server cache directory; library use stays in memory."""
    global _root
    _root = root


class ReadSnapshots:
    """Cache successful message windows for 15 seconds; never cache API errors."""

    def __init__(self, scope: str, realm: str, ttl: int = 15) -> None:
        self.realm = realm
        self.ttl = ttl
        self._memory = MessageCache(ttl=ttl, max_entries=64)
        self._flights = [threading.Lock() for _ in range(16)]
        self._state_lock = threading.Lock()
        self._generation = 0
        self.hits = 0
        self.misses = 0
        self.path: Path | None = None
        if _root is not None:
            _root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.path = _root / f"reads-{scope}.sqlite3"
            if self.path.is_symlink():
                raise ValueError("Read snapshot cache must not be a symlink")
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(fd)
            os.chmod(self.path, 0o600)
            with self._connect() as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS snapshots("
                    "key TEXT PRIMARY KEY,payload TEXT NOT NULL,captured REAL NOT NULL)"
                )
        with _instances_lock:
            _instances.add(self)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        assert self.path is not None
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def invalidate(self) -> None:
        with self._state_lock:
            self._generation += 1
            self._memory.clear()
            if self.path:
                try:
                    with self._connect() as db:
                        db.execute("DELETE FROM snapshots")
                except sqlite3.Error:
                    # A cache error after a delivered message must not suggest
                    # that sending failed and invite an unsafe duplicate retry.
                    self.path = None

    def fetch(
        self,
        request: dict[str, Any],
        loader: Callable[[], dict[str, Any]],
        use_cache: bool = True,
    ) -> dict[str, Any]:
        key = hashlib.sha256(
            json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self._flights[int(key[:4], 16) % len(self._flights)]:
            with self._state_lock:
                generation = self._generation
            now = time.time()
            saved = self._memory.get(key) if use_cache else None
            if saved is None and use_cache and self.path:
                try:
                    with self._connect() as db:
                        row = db.execute(
                            "SELECT payload,captured FROM snapshots WHERE key=?", (key,)
                        ).fetchone()
                    if row and 0 <= now - row[1] < self.ttl:
                        saved = (json.loads(row[0]), row[1])
                        self._memory.set(key, saved)
                except (sqlite3.Error, ValueError):
                    # Read caching is optional; a damaged cache never replaces
                    # a real upstream response with a false successful result.
                    saved = None
            hit = saved is not None
            if hit:
                assert saved is not None
                self.hits += 1
                response, captured = saved
            else:
                self.misses += 1
                response = loader()
                captured = time.time()
                if response.get("result") != "success":
                    return response
                encoded = json.dumps(response, sort_keys=True, separators=(",", ":"))
                with self._state_lock:
                    if (
                        use_cache
                        and generation == self._generation
                        and len(encoded.encode()) <= 524288
                    ):
                        self._memory.set(key, (deepcopy(response), captured))
                        if self.path and len(encoded.encode()) <= 524288:
                            try:
                                with self._connect() as db:
                                    db.execute(
                                        "INSERT OR REPLACE INTO snapshots VALUES(?,?,?)",
                                        (key, encoded, captured),
                                    )
                                    db.execute(
                                        "DELETE FROM snapshots WHERE key IN ("
                                        "SELECT key FROM snapshots ORDER BY captured DESC "
                                        "LIMIT -1 OFFSET 64)"
                                    )
                            except sqlite3.Error:
                                pass
            output = deepcopy(response)
            output["_cache"] = {
                "hit": hit,
                "age_seconds": round(max(0, time.time() - captured), 3),
                "max_age_seconds": self.ttl if use_cache else 0,
                "captured_at_utc": datetime.fromtimestamp(
                    captured, tz=timezone.utc
                ).isoformat(),
                "snapshot_id": hashlib.sha256(
                    json.dumps(response, sort_keys=True).encode()
                ).hexdigest(),
                "coverage": "single_api_window",
            }
            return output


def invalidate_realm_snapshots(realm: str) -> None:
    """Expire read windows on a same-process message mutation or event."""
    with _instances_lock:
        instances = [instance for instance in _instances if instance.realm == realm]
    for instance in instances:
        instance.invalidate()
