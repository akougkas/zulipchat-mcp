"""Database management for agent communication system."""

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentDatabase:
    """SQLite database for agent registry and task tracking."""

    def __init__(self, db_path: str = "zulipchat_agents.db"):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create agents table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    stream_id INTEGER,
                    stream_name TEXT,
                    bot_email TEXT,
                    webhook_url TEXT,
                    is_private BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    metadata TEXT
                )
                """
            )

            # Create tasks table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT REFERENCES agents(id),
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT CHECK(status IN ('pending','active','completed','failed','cancelled')),
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    output_summary TEXT,
                    outputs TEXT,
                    metrics TEXT,
                    progress_percentage INTEGER,
                    estimated_time TEXT,
                    zulip_topic TEXT
                )
                """
            )

            # Create input_requests table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS input_requests (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT REFERENCES agents(id),
                    question TEXT NOT NULL,
                    context TEXT,
                    options TEXT,
                    timeout_seconds INTEGER DEFAULT 300,
                    response TEXT,
                    is_answered BOOLEAN DEFAULT 0,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    responded_at TIMESTAMP,
                    user_email TEXT
                )
                """
            )

            # Create agent_messages table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT REFERENCES agents(id),
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    zulip_message_id INTEGER
                )
                """
            )

            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_requests_agent ON input_requests(agent_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_agent ON agent_messages(agent_id)"
            )

            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def register_agent(
        self,
        agent_id: str,
        name: str,
        agent_type: str,
        stream_id: int | None = None,
        stream_name: str | None = None,
        bot_email: str | None = None,
        webhook_url: str | None = None,
        is_private: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Register a new agent."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO agents (
                        id, name, type, stream_id, stream_name, 
                        bot_email, webhook_url, is_private, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agent_id,
                        name,
                        agent_type,
                        stream_id,
                        stream_name,
                        bot_email,
                        webhook_url,
                        is_private,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.error(f"Agent {agent_id} already exists")
                return False

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_agent_activity(self, agent_id: str) -> None:
        """Update agent's last active timestamp."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE agents SET last_active = ? WHERE id = ?",
                (datetime.now().isoformat(), agent_id),
            )
            conn.commit()

    def create_task(
        self,
        task_id: str,
        agent_id: str,
        name: str,
        description: str,
        subtasks: list[str] | None = None,
    ) -> bool:
        """Create a new task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO tasks (
                        id, agent_id, name, description, status, started_at
                    ) VALUES (?, ?, ?, ?, 'active', ?)
                    """,
                    (task_id, agent_id, name, description, datetime.now().isoformat()),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to create task: {e}")
                return False

    def update_task_progress(
        self,
        task_id: str,
        progress_percentage: int | None = None,
        estimated_time: str | None = None,
        status: str | None = None,
    ) -> bool:
        """Update task progress."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            values = []

            if progress_percentage is not None:
                updates.append("progress_percentage = ?")
                values.append(progress_percentage)

            if estimated_time is not None:
                updates.append("estimated_time = ?")
                values.append(estimated_time)

            if status is not None:
                updates.append("status = ?")
                values.append(status)

            if not updates:
                return False

            values.append(task_id)
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0

    def complete_task(
        self,
        task_id: str,
        summary: str,
        outputs: dict[str, Any],
        metrics: dict[str, Any] | None = None,
    ) -> bool:
        """Mark task as completed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks SET 
                    status = 'completed',
                    completed_at = ?,
                    output_summary = ?,
                    outputs = ?,
                    metrics = ?
                WHERE id = ?
                """,
                (
                    datetime.now().isoformat(),
                    summary,
                    json.dumps(outputs),
                    json.dumps(metrics) if metrics else None,
                    task_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def create_input_request(
        self,
        request_id: str,
        agent_id: str,
        question: str,
        context: dict[str, Any],
        options: list[str] | None = None,
        timeout_seconds: int = 300,
    ) -> bool:
        """Create a new input request."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO input_requests (
                        id, agent_id, question, context, options, timeout_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        agent_id,
                        question,
                        json.dumps(context),
                        json.dumps(options) if options else None,
                        timeout_seconds,
                    ),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to create input request: {e}")
                return False

    def save_user_response(
        self, request_id: str, response: str, user_email: str | None = None
    ) -> bool:
        """Save user response to an input request."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE input_requests SET 
                    response = ?,
                    is_answered = 1,
                    responded_at = ?,
                    user_email = ?
                WHERE id = ?
                """,
                (response, datetime.now().isoformat(), user_email, request_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_pending_request(self, request_id: str) -> dict[str, Any] | None:
        """Get a pending input request."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM input_requests WHERE id = ? AND is_answered = 0",
                (request_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def save_agent_message(
        self,
        message_id: str,
        agent_id: str,
        message_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        zulip_message_id: int | None = None,
    ) -> bool:
        """Save an agent message."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO agent_messages (
                        id, agent_id, message_type, content, metadata, zulip_message_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        agent_id,
                        message_type,
                        content,
                        json.dumps(metadata) if metadata else None,
                        zulip_message_id,
                    ),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to save agent message: {e}")
                return False

    def get_active_tasks(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        """Get active tasks, optionally filtered by agent."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if agent_id:
                cursor.execute(
                    "SELECT * FROM tasks WHERE agent_id = ? AND status = 'active'",
                    (agent_id,),
                )
            else:
                cursor.execute("SELECT * FROM tasks WHERE status = 'active'")
            return [dict(row) for row in cursor.fetchall()]
