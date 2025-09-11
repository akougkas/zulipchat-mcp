"""High-level DatabaseManager providing typed operations over DuckDB.

This wraps the lower-level connection from `utils.database.get_database()`
to provide convenient methods used by tools and services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .database import get_database
from .logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database operations with a simple, explicit API."""

    def __init__(self) -> None:
        # Reuse the existing singleton connection
        self._db = get_database()
        self.conn = self._db.conn

    # Low-level passthroughs (for legacy usage during migration)
    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        self._db.execute(sql, params or [])

    def query(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> List[tuple[Any, ...]]:
        return self._db.query(sql, params or [])

    def query_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> Optional[tuple[Any, ...]]:
        return self._db.query_one(sql, params or [])

    # Agent operations
    def create_agent_instance(
        self,
        agent_id: str,
        agent_type: str,
        project_name: str,
        **kwargs: Any,
    ) -> dict:
        try:
            self._db.execute(
                """
                INSERT INTO agent_instances 
                (instance_id, agent_id, session_id, project_dir, host, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    kwargs.get("instance_id"),
                    agent_id,
                    kwargs.get("session_id"),
                    kwargs.get("project_dir"),
                    kwargs.get("host"),
                    datetime.utcnow(),
                ],
            )
            return {"status": "success", "agent_id": agent_id}
        except Exception as e:
            logger.error(f"Failed to create agent instance: {e}")
            return {"status": "error", "error": str(e)}

    def get_agent_instance(self, agent_id: str) -> Optional[dict]:
        try:
            cursor = self.conn.execute(
                "SELECT * FROM agent_instances WHERE agent_id = ? ORDER BY started_at DESC LIMIT 1",
                [agent_id],
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [d[0] for d in cursor.description]
            return dict(zip(columns, row))
        except Exception as e:
            logger.error(f"Failed to get agent instance: {e}")
            return None

    # User input requests
    def create_input_request(
        self,
        request_id: str,
        agent_id: str,
        question: str,
        **kwargs: Any,
    ) -> dict:
        try:
            self._db.execute(
                """
                INSERT INTO user_input_requests
                (request_id, agent_id, question, options, context, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                [
                    request_id,
                    agent_id,
                    question,
                    kwargs.get("options"),
                    kwargs.get("context"),
                    datetime.utcnow(),
                ],
            )
            return {"status": "success", "request_id": request_id}
        except Exception as e:
            logger.error(f"Failed to create input request: {e}")
            return {"status": "error", "error": str(e)}

    def get_input_request(self, request_id: str) -> Optional[dict]:
        try:
            cursor = self.conn.execute(
                "SELECT * FROM user_input_requests WHERE request_id = ?",
                [request_id],
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [d[0] for d in cursor.description]
            return dict(zip(columns, row))
        except Exception as e:
            logger.error(f"Failed to get input request: {e}")
            return None

    def get_pending_input_requests(self) -> List[dict]:
        try:
            cursor = self.conn.execute(
                "SELECT * FROM user_input_requests WHERE status = 'pending'"
            )
            rows = cursor.fetchall() or []
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, r)) for r in rows]
        except Exception as e:
            logger.error(f"Failed to list pending input requests: {e}")
            return []

    def update_input_request(self, request_id: str, **updates: Any) -> dict:
        try:
            if not updates:
                return {"status": "success"}
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [request_id]
            self._db.execute(
                f"UPDATE user_input_requests SET {set_clause} WHERE request_id = ?",
                values,
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to update input request: {e}")
            return {"status": "error", "error": str(e)}

    # Task operations
    def create_task(self, task_id: str, agent_id: str, name: str, **kwargs: Any) -> dict:
        try:
            self._db.execute(
                """
                INSERT INTO tasks
                (task_id, agent_id, name, description, status, progress, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    task_id,
                    agent_id,
                    name,
                    kwargs.get("description", ""),
                    kwargs.get("status", "started"),
                    kwargs.get("progress", 0),
                    datetime.utcnow(),
                ],
            )
            return {"status": "success", "task_id": task_id}
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return {"status": "error", "error": str(e)}

    def update_task(self, task_id: str, **updates: Any) -> dict:
        try:
            if not updates:
                return {"status": "success"}
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [task_id]
            self._db.execute(
                f"UPDATE tasks SET {set_clause} WHERE task_id = ?",
                values,
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            return {"status": "error", "error": str(e)}

    # AFK state
    def get_afk_state(self) -> Optional[dict]:
        try:
            cursor = self.conn.execute(
                "SELECT * FROM afk_state ORDER BY updated_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [d[0] for d in cursor.description]
            return dict(zip(columns, row))
        except Exception as e:
            logger.error(f"Failed to get AFK state: {e}")
            return None

    def set_afk_state(self, enabled: bool, reason: str = "", hours: int = 0) -> dict:
        try:
            # Clear existing state and insert new
            self._db.execute("DELETE FROM afk_state")
            self._db.execute(
                """
                INSERT INTO afk_state (id, is_afk, reason, auto_return_at, updated_at)
                VALUES (1, ?, ?, NULL, ?)
                """,
                [enabled, reason, datetime.utcnow()],
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to set AFK state: {e}")
            return {"status": "error", "error": str(e)}

    # Agent status audit trail
    def create_agent_status(self, status_id: str, agent_type: str, status: str, message: str = "") -> dict:
        try:
            self._db.execute(
                """
                INSERT INTO agent_status (status_id, agent_type, status, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [status_id, agent_type, status, message, datetime.utcnow()],
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to create agent status: {e}")
            return {"status": "error", "error": str(e)}

    # Agent chat events
    def create_agent_event(
        self,
        event_id: str,
        zulip_message_id: int | None,
        topic: str,
        sender_email: str,
        content: str,
    ) -> dict:
        try:
            self._db.execute(
                """
                INSERT INTO agent_events (id, zulip_message_id, topic, sender_email, content, created_at, acked)
                VALUES (?, ?, ?, ?, ?, ?, FALSE)
                """,
                [event_id, zulip_message_id, topic, sender_email, content, datetime.utcnow()],
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to create agent event: {e}")
            return {"status": "error", "error": str(e)}

    def get_unacked_events(self, limit: int = 50, topic_prefix: str | None = None) -> list[dict]:
        try:
            if topic_prefix:
                cursor = self.conn.execute(
                    "SELECT * FROM agent_events WHERE acked = FALSE AND topic LIKE ? ORDER BY created_at DESC LIMIT ?",
                    [f"{topic_prefix}%", limit],
                )
            else:
                cursor = self.conn.execute(
                    "SELECT * FROM agent_events WHERE acked = FALSE ORDER BY created_at DESC LIMIT ?",
                    [limit],
                )
            rows = cursor.fetchall() or []
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch unacked events: {e}")
            return []

    def ack_events(self, ids: list[str]) -> dict:
        try:
            if not ids:
                return {"status": "success"}
            placeholders = ",".join(["?"] * len(ids))
            self._db.execute(
                f"UPDATE agent_events SET acked = TRUE WHERE id IN ({placeholders})",
                ids,
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to ack events: {e}")
            return {"status": "error", "error": str(e)}
