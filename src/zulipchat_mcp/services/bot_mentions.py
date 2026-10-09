"""Account-scoped, durable bot mention and direct-message snapshots fed by Zulip.

This is a transport inbox, not an agent runner. The tool layer withholds content
from unauthorized senders; hosts still commit their own message-ID cursor with
their work queue. One inbox serves one scope: a channel's @-mentions of the bot,
or every direct and group-direct message the bot receives (stream is None).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..core.client import ZulipClientWrapper
from ..core.process_lease import ProcessLease
from ..core.snapshots import invalidate_realm_snapshots


class BotMentionInbox:
    """One lazy event queue and bounded snapshot for one account and scope."""

    def __init__(
        self,
        client: ZulipClientWrapper,
        path: Path,
        account_fingerprint: str,
        stream: str | None,
        initial_cursor: int | None = None,
    ) -> None:
        self.client = client
        self.path = path
        self.stream = stream
        self.direct = stream is None
        self.initial_cursor = initial_cursor
        self._condition = threading.Condition(threading.RLock())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ready = False
        self._error: str | None = None
        self._retry_after = 0.0
        self._bot_id: int | None = None
        self._history_requests = 0
        self._event_requests = 0
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError("Mention cache must not be a symlink")
        # Restrict new files before SQLite also creates its WAL/SHM files.
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS messages(
                    id INTEGER PRIMARY KEY, payload TEXT NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0
                );
                """)
            bound = db.execute(
                "SELECT value FROM metadata WHERE key='account'"
            ).fetchone()
            if bound and bound[0] != account_fingerprint:
                raise ValueError("Mention cache account mismatch")
            db.execute(
                "INSERT OR IGNORE INTO metadata VALUES('account', ?)",
                (account_fingerprint,),
            )
        self._bot_id = self._state("bot_user_id")
        self._bot_verified = False

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _state(self, key: str) -> Any:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM metadata WHERE key=?", (key,)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def _accepts(self, message: dict[str, Any]) -> bool:
        """Whether a message belongs in this inbox's scope."""
        # The bot's own replies must never come back as new work, including a
        # reply that @-mentions the bot itself.
        if message.get("sender_id") == self._bot_id:
            return False
        if self.direct:
            return message.get("type") == "private"
        return "mentioned" in message.get("flags", [])

    def _narrows(self) -> tuple[list[list[str]], list[dict[str, str]]]:
        """Event-queue narrow and equivalent history narrow for this scope."""
        if not self.direct:
            return (
                [["stream", str(self.stream)]],
                [
                    {"operator": "stream", "operand": str(self.stream)},
                    {"operator": "is", "operand": "mentioned"},
                ],
            )
        # Zulip 7.0 (feature level 177) replaced is:private with is:dm. Both are
        # supported by event-queue narrows; older servers only know is:private.
        level = getattr(self.client.client, "feature_level", 0)
        operand = "private" if isinstance(level, int) and 0 < level < 177 else "dm"
        return (
            [["is", operand]],
            [{"operator": "is", "operand": operand}],
        )

    def _commit(
        self,
        messages: list[dict[str, Any]],
        state: dict[str, Any],
        deleted_ids: list[int] | None = None,
    ) -> None:
        """Persist message deltas and the upstream cursor in one transaction."""
        with self._condition, self._connect() as db:
            for message in messages:
                if not self._accepts(message):
                    continue
                message_id = message["id"]
                if type(message_id) is not int or message_id <= 0:
                    raise ValueError("Invalid Zulip message ID")
                payload = dict(message)
                content = str(payload.get("content", ""))
                payload["content"] = content[:6000]
                payload["content_truncated"] = len(content) > 6000
                db.execute(
                    "INSERT INTO messages(id, payload) VALUES(?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                    (message_id, json.dumps(payload)),
                )
            for message_id in deleted_ids or []:
                db.execute(
                    "UPDATE messages SET deleted=1,payload='{}' WHERE id=?",
                    (message_id,),
                )
            for key, value in state.items():
                db.execute(
                    "INSERT OR REPLACE INTO metadata VALUES(?, ?)",
                    (key, json.dumps(value)),
                )
            # Keep a bounded rolling snapshot; detect consumers behind retention.
            cutoff = db.execute(
                "SELECT id FROM messages ORDER BY id DESC LIMIT 1 OFFSET 9999"
            ).fetchone()
            if cutoff:
                db.execute("DELETE FROM messages WHERE id < ?", (cutoff[0],))
                db.execute(
                    "INSERT OR REPLACE INTO metadata VALUES('retention_floor', ?)",
                    (json.dumps(cutoff[0]),),
                )
        with self._condition:
            self._condition.notify_all()

    def _bootstrap(self) -> None:
        """Register before backfill so messages arriving during it are replayed."""
        if not self._bot_verified:
            profile = self.client.client.get_profile()
            self._check_response(profile)
            if not profile.get("is_bot") or profile.get("bot_type") != 1:
                raise RuntimeError("Mention listening requires a Generic bot account")
            if self._bot_id is not None and self._bot_id != profile["user_id"]:
                raise RuntimeError(
                    "Bot account ID changed; verify pairing and use a new cache"
                )
            self._bot_id = profile["user_id"]
            self._commit([], {"bot_user_id": self._bot_id})
            self._bot_verified = True
        if self._state("queue_id"):
            return
        event_narrow, history_narrow = self._narrows()
        # Zulip applies a queue narrow to message events only; update_message and
        # delete_message arrive unfiltered and merely tombstone known IDs here.
        response = self.client.register(
            event_types=["message", "update_message", "delete_message"],
            narrow=event_narrow,
            apply_markdown=False,
        )
        self._check_response(response)
        queue_id = response["queue_id"]
        cursor = self._state("message_cursor")
        if cursor is None:
            cursor = self.initial_cursor
        try:
            for _ in range(20):
                self._history_requests += 1
                history = self.client.get_messages_raw(
                    narrow=history_narrow,
                    anchor=str(cursor) if cursor is not None else "newest",
                    num_before=50 if cursor is None else 0,
                    num_after=50 if cursor is not None else 0,
                    include_anchor=cursor is None,
                    apply_markdown=False,
                    use_cache=False,
                )
                self._check_response(history)
                messages = history.get("messages", [])
                next_cursor = max(
                    (message["id"] for message in messages), default=cursor or 0
                )
                self._commit(messages, {"message_cursor": next_cursor})
                if cursor is None or history.get("found_newest") or not messages:
                    break
                if next_cursor <= cursor:
                    raise RuntimeError("Mention backfill cursor did not advance")
                cursor = next_cursor
            else:
                raise RuntimeError("Mention recovery page budget reached; retry later")
            self._commit(
                [],
                {"queue_id": queue_id, "last_event_id": response["last_event_id"]},
            )
        except Exception:
            self.client.deregister(queue_id, timeout=5)
            raise

    def _check_response(self, response: dict[str, Any]) -> None:
        if response.get("result") != "success":
            retry = response.get("retry-after", response.get("retry_after", 0))
            try:
                self._retry_after = max(0, float(retry))
            except (ValueError, TypeError):
                self._retry_after = 0
            raise RuntimeError(str(response.get("code") or response.get("msg")))
        self._retry_after = 0

    def _ingest_events(self, events: list[dict[str, Any]]) -> None:
        if events:
            invalidate_realm_snapshots(self.client.base_url)
        for event in events:
            messages = []
            deleted: list[int] = []
            state = {"last_event_id": event["id"]}
            if event.get("type") == "message":
                message = {**event["message"], "flags": event.get("flags", [])}
                if message.get("type") == ("private" if self.direct else "stream"):
                    messages.append(message)
                    state["message_cursor"] = max(
                        self._state("message_cursor") or 0, message["id"]
                    )
            elif event.get("type") == "update_message" and event.get("rendering_only"):
                # Server-side rendering (e.g. link previews) did not change the text.
                pass
            elif event.get("type") in {"update_message", "delete_message"}:
                # Changed input must not silently become a new executable task.
                # Remove it from the inbox; edits can be fetched explicitly.
                deleted = event.get("message_ids") or [event.get("message_id")]
                deleted = [value for value in deleted if type(value) is int]
            self._commit(messages, state, deleted)

    def _run(self) -> None:
        try:
            with ProcessLease(self.path.with_suffix(".lock")):
                self._run_owned()
        except Exception as error:
            with self._condition:
                self._ready = False
                self._error = str(error)
                self._condition.notify_all()

    def _run_owned(self) -> None:
        failures = 0
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self._bootstrap()
                with self._condition:
                    self._ready = True
                    self._error = None
                    self._condition.notify_all()
                self._event_requests += 1
                response = self.client.get_events(
                    queue_id=self._state("queue_id"),
                    last_event_id=self._state("last_event_id"),
                    dont_block=False,
                    timeout=90,
                )
                if self._stop.is_set():
                    break
                if response.get("code") == "BAD_EVENT_QUEUE_ID":
                    self._commit([], {"queue_id": None})
                self._check_response(response)
                self._ingest_events(response.get("events", []))
                failures = 0
                self._stop.wait(max(0, 0.5 - (time.monotonic() - started)))
            except Exception as error:
                failures += 1
                with self._condition:
                    self._ready = False
                    self._error = str(error)
                    self._condition.notify_all()
                delay = max(self._retry_after, min(120, 2 ** min(failures, 7)))
                self._stop.wait(delay)

    def start(self) -> None:
        with self._condition:
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._run,
                    name="zulip-bot-direct" if self.direct else "zulip-bot-mentions",
                    daemon=True,
                )
                self._thread.start()

    def poll(
        self, after_message_id: int | None, limit: int, wait_seconds: float = 0
    ) -> dict[str, Any]:
        self.start()
        deadline = time.monotonic() + max(wait_seconds, 20 if not self._ready else 0)
        with self._condition:
            while True:
                with self._connect() as db:
                    rows = db.execute(
                        "SELECT id,payload,deleted FROM messages WHERE id > ? "
                        "ORDER BY id LIMIT ?",
                        (after_message_id or 0, limit),
                    ).fetchall()
                if rows or self._error or (self._ready and wait_seconds == 0):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
        floor = self._state("retention_floor")
        gap = floor is not None and (after_message_id or 0) < floor
        return {
            "status": "partial" if gap or self._error or not self._ready else "success",
            "mode": "bot_direct_messages" if self.direct else "bot_mentions",
            "messages": [json.loads(row[1]) for row in rows if not row[2]],
            "next_after_message_id": max(
                (row[0] for row in rows), default=after_message_id
            ),
            "bot_user_id": self._bot_id,
            "listener": {
                "ready": self._ready,
                "error": self._error,
                "retry_after_seconds": math.ceil(self._retry_after),
            },
            "cache": {
                "source": "local_snapshot_and_event_deltas",
                "history_requests": self._history_requests,
                "event_requests": self._event_requests,
                "retention_limit": 10000,
                "cursor_gap": gap,
            },
            "acknowledgement": "host_owned_message_id_cursor",
        }

    def stop(self) -> None:
        self._stop.set()
        queue_id = self._state("queue_id")
        if queue_id:
            try:
                self.client.deregister(queue_id, timeout=5)
                self._commit([], {"queue_id": None})
            except Exception:
                # Retain the queue identity for replay on a same-account restart.
                pass


_inboxes: dict[tuple[str, str, str | None], BotMentionInbox] = {}
_inboxes_lock = threading.Lock()


def get_mention_inbox(
    client: ZulipClientWrapper,
    account_fingerprint: str,
    stream: str | None,
    initial_cursor: int | None,
) -> BotMentionInbox:
    from ..utils.database import get_database

    base = str(Path(get_database().db_path).resolve().parent / "cache")
    key = (base, account_fingerprint, stream)
    with _inboxes_lock:
        if key not in _inboxes:
            if stream is None:
                # Direct messages have their own cache file, queue and lease.
                path = Path(base) / f"direct-{account_fingerprint}.sqlite3"
            else:
                if sum(1 for _, _, scope in _inboxes if scope is not None) >= 4:
                    raise ValueError(
                        "At most four mention channels per server are supported"
                    )
                digest = hashlib.sha256(stream.encode()).hexdigest()[:16]
                path = Path(base) / f"mentions-{account_fingerprint}-{digest}.sqlite3"
            _inboxes[key] = BotMentionInbox(
                client, path, account_fingerprint, stream, initial_cursor
            )
        return _inboxes[key]


def shutdown_mention_inboxes() -> None:
    with _inboxes_lock:
        for inbox in _inboxes.values():
            inbox.stop()
        _inboxes.clear()
