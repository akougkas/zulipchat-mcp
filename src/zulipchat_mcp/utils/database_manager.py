"""High-level DatabaseManager providing typed operations over DuckDB.

This wraps the lower-level connection from `utils.database.get_database()`
to provide convenient methods used by tools and services.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .database import get_database
from .logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database operations with a simple, explicit API.

    Uses short-lived connections to support concurrent access from multiple
    MCP server instances.
    """

    def __init__(self) -> None:
        # Reuse the existing singleton for configuration
        self._db = get_database()

    # Agent profile and session control plane
    def upsert_agent_profile(
        self,
        agent_id: str,
        agent_name: str,
        agent_type: str,
        owner_email: str,
        stream_name: str,
        topic_prefix: str,
        metadata: str = "{}",
    ) -> dict[str, Any]:
        try:
            now = datetime.now(timezone.utc)
            existing = self._db.query_one_as_dict(
                "SELECT agent_id, created_at FROM agent_profiles WHERE agent_id = ?",
                [agent_id],
            )
            created_at = (
                existing.get("created_at")
                if existing and existing.get("created_at") is not None
                else now
            )
            self._db.execute(
                """
                INSERT OR REPLACE INTO agent_profiles
                (agent_id, agent_name, agent_type, owner_email, stream_name, topic_prefix, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    agent_id,
                    agent_name,
                    agent_type,
                    owner_email,
                    stream_name,
                    topic_prefix,
                    metadata,
                    created_at,
                    now,
                ],
            )
            return {"status": "success", "agent_id": agent_id}
        except Exception as e:
            logger.error(f"Failed to upsert agent profile: {e}")
            return {"status": "error", "error": str(e)}

    def get_agent_profile(self, agent_id: str) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                "SELECT * FROM agent_profiles WHERE agent_id = ?",
                [agent_id],
            )
        except Exception as e:
            logger.error(f"Failed to get agent profile: {e}")
            return None

    def get_agent_profile_by_name(
        self, agent_name: str, owner_email: str
    ) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                """
                SELECT * FROM agent_profiles
                WHERE agent_name = ? AND owner_email = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                [agent_name, owner_email],
            )
        except Exception as e:
            logger.error(f"Failed to get agent profile by name: {e}")
            return None

    def list_agent_profiles(self) -> list[dict[str, Any]]:
        try:
            return self._db.query_as_dicts(
                "SELECT * FROM agent_profiles ORDER BY updated_at DESC"
            )
        except Exception as e:
            logger.error(f"Failed to list agent profiles: {e}")
            return []

    def upsert_agent_session(
        self,
        session_id: str,
        agent_id: str,
        stream_name: str,
        topic_name: str,
        owner_email: str,
        status: str,
        external_session_id: str | None = None,
        project_name: str | None = None,
        project_dir: str | None = None,
        host: str | None = None,
        metadata: str = "{}",
    ) -> dict[str, Any]:
        try:
            now = datetime.now(timezone.utc)
            existing = self._db.query_one_as_dict(
                "SELECT session_id, created_at FROM agent_sessions WHERE session_id = ?",
                [session_id],
            )
            created_at = (
                existing.get("created_at")
                if existing and existing.get("created_at") is not None
                else now
            )
            self._db.execute(
                """
                INSERT OR REPLACE INTO agent_sessions
                (session_id, agent_id, external_session_id, stream_name, topic_name, owner_email,
                 project_name, project_dir, host, status, metadata, created_at, updated_at, ended_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    session_id,
                    agent_id,
                    external_session_id,
                    stream_name,
                    topic_name,
                    owner_email,
                    project_name,
                    project_dir,
                    host,
                    status,
                    metadata,
                    created_at,
                    now,
                    None if status not in {"completed", "failed", "cancelled"} else now,
                ],
            )
            return {"status": "success", "session_id": session_id}
        except Exception as e:
            logger.error(f"Failed to upsert agent session: {e}")
            return {"status": "error", "error": str(e)}

    def get_agent_session(self, session_id: str) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                "SELECT * FROM agent_sessions WHERE session_id = ?",
                [session_id],
            )
        except Exception as e:
            logger.error(f"Failed to get agent session: {e}")
            return None

    def get_agent_session_by_external(
        self, agent_id: str, external_session_id: str
    ) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                """
                SELECT * FROM agent_sessions
                WHERE agent_id = ? AND external_session_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                [agent_id, external_session_id],
            )
        except Exception as e:
            logger.error(f"Failed to get session by external ID: {e}")
            return None

    def get_agent_session_for_topic(
        self, stream_name: str, topic_name: str
    ) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                """
                SELECT * FROM agent_sessions
                WHERE stream_name = ? AND topic_name = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                [stream_name, topic_name],
            )
        except Exception as e:
            logger.error(f"Failed to get session for topic: {e}")
            return None

    def get_latest_agent_session(
        self, agent_id: str, project_dir: str | None = None
    ) -> dict[str, Any] | None:
        try:
            if project_dir:
                return self._db.query_one_as_dict(
                    """
                    SELECT * FROM agent_sessions
                    WHERE agent_id = ? AND project_dir = ? AND ended_at IS NULL
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    [agent_id, project_dir],
                )
            return self._db.query_one_as_dict(
                """
                SELECT * FROM agent_sessions
                WHERE agent_id = ? AND ended_at IS NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                [agent_id],
            )
        except Exception as e:
            logger.error(f"Failed to get latest agent session: {e}")
            return None

    def list_agent_sessions(
        self, agent_id: str | None = None, include_closed: bool = True
    ) -> list[dict[str, Any]]:
        try:
            sql = "SELECT * FROM agent_sessions"
            params: list[Any] = []
            clauses: list[str] = []
            if agent_id:
                clauses.append("agent_id = ?")
                params.append(agent_id)
            if not include_closed:
                clauses.append("ended_at IS NULL")
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY updated_at DESC"
            return self._db.query_as_dicts(sql, params)
        except Exception as e:
            logger.error(f"Failed to list agent sessions: {e}")
            return []

    def update_agent_session(self, session_id: str, **updates: Any) -> dict[str, Any]:
        try:
            payload = dict(updates)
            payload["updated_at"] = datetime.now(timezone.utc)
            if payload.get("status") in {"completed", "failed", "cancelled"}:
                payload.setdefault("ended_at", datetime.now(timezone.utc))
            elif "status" in payload:
                payload.setdefault("ended_at", None)
            if not payload:
                return {"status": "success"}
            set_clause = ", ".join([f"{k} = ?" for k in payload.keys()])
            values = list(payload.values()) + [session_id]
            self._db.execute(
                f"UPDATE agent_sessions SET {set_clause} WHERE session_id = ?",
                values,
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to update agent session: {e}")
            return {"status": "error", "error": str(e)}

    def create_agent_request(
        self,
        request_id: str,
        agent_id: str,
        session_id: str,
        request_type: str,
        prompt: str,
        options: str | None = None,
        context: str = "",
        source_event: str = "",
        metadata: str = "{}",
    ) -> dict[str, Any]:
        try:
            self._db.execute(
                """
                INSERT INTO agent_requests
                (request_id, agent_id, session_id, request_type, prompt, options, context,
                 status, source_event, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                [
                    request_id,
                    agent_id,
                    session_id,
                    request_type,
                    prompt,
                    options,
                    context,
                    source_event,
                    metadata,
                    datetime.now(timezone.utc),
                ],
            )
            return {"status": "success", "request_id": request_id}
        except Exception as e:
            logger.error(f"Failed to create agent request: {e}")
            return {"status": "error", "error": str(e)}

    def get_agent_request(self, request_id: str) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                "SELECT * FROM agent_requests WHERE request_id = ?",
                [request_id],
            )
        except Exception as e:
            logger.error(f"Failed to get agent request: {e}")
            return None

    def get_latest_pending_request(
        self, session_id: str, request_type: str | None = None
    ) -> dict[str, Any] | None:
        try:
            sql = """
                SELECT * FROM agent_requests
                WHERE session_id = ? AND status = 'pending'
            """
            params: list[Any] = [session_id]
            if request_type:
                sql += " AND request_type = ?"
                params.append(request_type)
            sql += " ORDER BY created_at DESC LIMIT 1"
            return self._db.query_one_as_dict(sql, params)
        except Exception as e:
            logger.error(f"Failed to get latest pending request: {e}")
            return None

    def update_agent_request(self, request_id: str, **updates: Any) -> dict[str, Any]:
        """Transition a pending request once; terminal decisions are immutable."""
        try:
            if not updates:
                return {"status": "success"}
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [request_id]
            self._db.execute(
                f"UPDATE agent_requests SET {set_clause} WHERE request_id = ? AND status = 'pending'",
                values,
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to update agent request: {e}")
            return {"status": "error", "error": str(e)}

    def create_session_event(
        self,
        event_id: str,
        direction: str,
        event_type: str,
        content: str,
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        stream_name: str | None = None,
        topic_name: str | None = None,
        sender_email: str | None = None,
        normalized_content: str | None = None,
        command: str | None = None,
        decision: str | None = None,
        request_id: str | None = None,
        metadata: str = "{}",
    ) -> dict[str, Any]:
        try:
            self._db.execute(
                """
                INSERT INTO session_events
                (id, agent_id, session_id, stream_name, topic_name, sender_email, direction,
                 event_type, content, normalized_content, command, decision, request_id, metadata,
                 created_at, acked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    event_id,
                    agent_id,
                    session_id,
                    stream_name,
                    topic_name,
                    sender_email,
                    direction,
                    event_type,
                    content,
                    normalized_content,
                    command,
                    decision,
                    request_id,
                    metadata,
                    datetime.now(timezone.utc),
                ],
            )
            return {"status": "success", "event_id": event_id}
        except Exception as e:
            logger.error(f"Failed to create session event: {e}")
            return {"status": "error", "error": str(e)}

    def get_unacked_session_events(
        self,
        limit: int = 50,
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            sql = "SELECT * FROM session_events WHERE acked = FALSE"
            params: list[Any] = []
            if agent_id:
                sql += " AND agent_id = ?"
                params.append(agent_id)
            if session_id:
                sql += " AND session_id = ?"
                params.append(session_id)
            if event_type:
                sql += " AND event_type = ?"
                params.append(event_type)
            sql += " ORDER BY created_at ASC LIMIT ?"
            params.append(limit)
            return self._db.query_as_dicts(sql, params)
        except Exception as e:
            logger.error(f"Failed to get unacked session events: {e}")
            return []

    def ack_session_events(self, ids: list[str]) -> dict[str, Any]:
        try:
            if not ids:
                return {"status": "success"}
            placeholders = ",".join(["?"] * len(ids))
            self._db.execute(
                f"UPDATE session_events SET acked = TRUE WHERE id IN ({placeholders})",
                ids,
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to ack session events: {e}")
            return {"status": "error", "error": str(e)}

    # Low-level passthroughs (for legacy usage during migration)
    def execute(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> None:
        self._db.execute(sql, params or [])

    def query(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        return self._db.query(sql, params or [])

    def query_one(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> tuple[Any, ...] | None:
        return self._db.query_one(sql, params or [])

    # Agent operations
    def create_agent_instance(
        self,
        agent_id: str,
        agent_type: str,
        project_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
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
                    datetime.now(timezone.utc),
                ],
            )
            return {"status": "success", "agent_id": agent_id}
        except Exception as e:
            logger.error(f"Failed to create agent instance: {e}")
            return {"status": "error", "error": str(e)}

    def get_agent_instance(self, agent_id: str) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                "SELECT * FROM agent_instances WHERE agent_id = ? ORDER BY started_at DESC LIMIT 1",
                [agent_id],
            )
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
    ) -> dict[str, Any]:
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
                    datetime.now(timezone.utc),
                ],
            )
            return {"status": "success", "request_id": request_id}
        except Exception as e:
            logger.error(f"Failed to create input request: {e}")
            return {"status": "error", "error": str(e)}

    def get_input_request(self, request_id: str) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                "SELECT * FROM user_input_requests WHERE request_id = ?",
                [request_id],
            )
        except Exception as e:
            logger.error(f"Failed to get input request: {e}")
            return None

    def get_pending_input_requests(self) -> list[dict[str, Any]]:
        try:
            return self._db.query_as_dicts(
                "SELECT * FROM user_input_requests WHERE status = 'pending'"
            )
        except Exception as e:
            logger.error(f"Failed to list pending input requests: {e}")
            return []

    def update_input_request(self, request_id: str, **updates: Any) -> dict[str, Any]:
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
    def create_task(
        self, task_id: str, agent_id: str, name: str, **kwargs: Any
    ) -> dict[str, Any]:
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
                    datetime.now(timezone.utc),
                ],
            )
            return {"status": "success", "task_id": task_id}
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return {"status": "error", "error": str(e)}

    def update_task(self, task_id: str, **updates: Any) -> dict[str, Any]:
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

    # Legacy AFK state helpers retained for backward compatibility.
    def get_afk_state(self) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                "SELECT * FROM afk_state ORDER BY updated_at DESC LIMIT 1"
            )
        except Exception as e:
            logger.error(f"Failed to get AFK state: {e}")
            return None

    def set_afk_state(
        self, enabled: bool, reason: str = "", hours: int = 0
    ) -> dict[str, Any]:
        try:
            now = datetime.now(timezone.utc)
            auto_return_at = (
                now + timedelta(hours=hours) if enabled and hours > 0 else None
            )
            # Clear existing state and insert new
            self._db.execute(
                """
                INSERT OR REPLACE INTO afk_state (id, is_afk, reason, auto_return_at, updated_at)
                VALUES (1, ?, ?, ?, ?)
                """,
                [enabled, reason, auto_return_at, now],
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to set AFK state: {e}")
            return {"status": "error", "error": str(e)}

    # Listener state persistence
    def save_listener_state(
        self, queue_id: str, last_event_id: int | None
    ) -> dict[str, Any]:
        try:
            self._db.execute(
                """
                INSERT OR REPLACE INTO listener_state (id, queue_id, last_event_id, updated_at)
                VALUES (1, ?, ?, ?)
                """,
                [queue_id, last_event_id, datetime.now(timezone.utc)],
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to save listener state: {e}")
            return {"status": "error", "error": str(e)}

    def get_listener_state(self) -> dict[str, Any] | None:
        try:
            return self._db.query_one_as_dict(
                "SELECT * FROM listener_state WHERE id = 1"
            )
        except Exception as e:
            logger.error(f"Failed to get listener state: {e}")
            return None

    # Agent status audit trail
    def create_agent_status(
        self, status_id: str, agent_type: str, status: str, message: str = ""
    ) -> dict[str, Any]:
        try:
            self._db.execute(
                """
                INSERT INTO agent_status (status_id, agent_type, status, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [status_id, agent_type, status, message, datetime.now(timezone.utc)],
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
    ) -> dict[str, Any]:
        try:
            self._db.execute(
                """
                INSERT INTO agent_events (id, zulip_message_id, topic, sender_email, content, created_at, acked)
                VALUES (?, ?, ?, ?, ?, ?, FALSE)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    event_id,
                    zulip_message_id,
                    topic,
                    sender_email,
                    content,
                    datetime.now(timezone.utc),
                ],
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to create agent event: {e}")
            return {"status": "error", "error": str(e)}

    def get_unacked_events(
        self, limit: int = 50, topic_prefix: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            if topic_prefix:
                return self._db.query_as_dicts(
                    "SELECT * FROM agent_events WHERE acked = FALSE AND topic LIKE ? ORDER BY created_at DESC LIMIT ?",
                    [f"{topic_prefix}%", limit],
                )
            else:
                return self._db.query_as_dicts(
                    "SELECT * FROM agent_events WHERE acked = FALSE ORDER BY created_at DESC LIMIT ?",
                    [limit],
                )
        except Exception as e:
            logger.error(f"Failed to fetch unacked events: {e}")
            return []

    def ack_events(self, ids: list[str]) -> dict[str, Any]:
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
