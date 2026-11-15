"""Durable bridge state for one agent bot, shared with its agent's MCP process.

conversations: Zulip conversation key -> ACP session, so a restarted agent
resumes the same session. turns: a journal of prompts in flight, so a crash
mid-turn is reported instead of silently replayed. questions: open permission
requests and owner questions; the owner's next message in that conversation
answers the oldest one instead of starting a new turn.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS conversations(
    key TEXT PRIMARY KEY, session_id TEXT, cwd TEXT NOT NULL, destination TEXT NOT NULL,
    updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS turns(
    message_id INTEGER PRIMARY KEY, key TEXT NOT NULL, status TEXT NOT NULL,
    started REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS questions(
    id TEXT PRIMARY KEY, key TEXT NOT NULL, kind TEXT NOT NULL, prompt TEXT NOT NULL,
    options TEXT NOT NULL, created REAL NOT NULL, deadline REAL NOT NULL,
    answer TEXT, answered REAL
);
"""


class BridgeStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        with self._db() as db:
            db.executescript(_SCHEMA)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    # Conversations
    def conversation(self, key: str) -> dict[str, Any] | None:
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM conversations WHERE key=?", (key,)
            ).fetchone()
        if not row:
            return None
        return {**dict(row), "destination": json.loads(row["destination"])}

    def bind(
        self, key: str, session_id: str | None, cwd: str, destination: dict[str, Any]
    ) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO conversations VALUES(?,?,?,?,?)",
                (key, session_id, cwd, json.dumps(destination), time.time()),
            )

    # Turns
    def start_turn(self, message_id: int, key: str) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO turns VALUES(?,?,'running',?)",
                (message_id, key, time.time()),
            )

    def finish_turn(self, message_id: int, status: str = "done") -> None:
        with self._db() as db:
            db.execute(
                "UPDATE turns SET status=? WHERE message_id=?", (status, message_id)
            )

    def interrupted_turns(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM turns WHERE status='running'").fetchall()
        return [dict(row) for row in rows]

    # Questions
    def ask(
        self, key: str, kind: str, prompt: str, options: list[str], minutes: float
    ) -> str:
        question_id = secrets.token_hex(2)
        now = time.time()
        with self._db() as db:
            db.execute(
                "INSERT INTO questions VALUES(?,?,?,?,?,?,?,NULL,NULL)",
                (
                    question_id,
                    key,
                    kind,
                    prompt,
                    json.dumps(options),
                    now,
                    now + minutes * 60,
                ),
            )
        return question_id

    def open_question(self, key: str) -> dict[str, Any] | None:
        """The oldest unanswered, unexpired question in a conversation."""
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM questions WHERE key=? AND answer IS NULL AND deadline>? "
                "ORDER BY created LIMIT 1",
                (key, time.time()),
            ).fetchone()
        return {**dict(row), "options": json.loads(row["options"])} if row else None

    def answer(self, question_id: str, answer: str) -> bool:
        """Record an answer once; False if already answered or expired."""
        with self._db() as db:
            changed = db.execute(
                "UPDATE questions SET answer=?, answered=? "
                "WHERE id=? AND answer IS NULL AND deadline>?",
                (answer, time.time(), question_id, time.time()),
            ).rowcount
        return changed == 1

    def close(self, question_id: str) -> bool:
        """Expire an unanswered question so the next message starts a turn."""
        with self._db() as db:
            changed = db.execute(
                "UPDATE questions SET deadline=? WHERE id=? AND answer IS NULL",
                (time.time(), question_id),
            ).rowcount
        return changed == 1

    def question(self, question_id: str) -> dict[str, Any] | None:
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM questions WHERE id=?", (question_id,)
            ).fetchone()
        return {**dict(row), "options": json.loads(row["options"])} if row else None
