"""DuckDB-backed persistence for ZulipChat MCP state and cache."""

import os
import threading
from datetime import datetime
from typing import Any

import duckdb


class DatabaseManager:
    """DuckDB database manager for ZulipChat MCP.

    Provides thread-safe database operations with automatic migrations
    and connection management.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize database manager with connection and migrations.

        Args:
            db_path: Path to the DuckDB database file
        """
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = duckdb.connect(db_path)
        self._write_lock = threading.RLock()
        self.run_migrations()

    def run_migrations(self) -> None:
        """Run all database migrations idempotently."""
        # Create migrations table
        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP
          );
        """
        )

        # Version 1 schema - Core tables for agent tracking and state
        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS afk_state(
            id INTEGER PRIMARY KEY,
            is_afk BOOLEAN NOT NULL,
            reason TEXT,
            auto_return_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL
          );
        """
        )

        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS agents(
            agent_id TEXT PRIMARY KEY,
            agent_type TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            metadata TEXT
          );
        """
        )

        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS agent_instances(
            instance_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            session_id TEXT,
            project_dir TEXT,
            host TEXT,
            started_at TIMESTAMP NOT NULL,
            FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
          );
        """
        )

        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS user_input_requests(
            request_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            question TEXT NOT NULL,
            context TEXT,
            options TEXT,
            status TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            responded_at TIMESTAMP,
            response TEXT
          );
        """
        )

        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS tasks(
            task_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            progress INTEGER,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            outputs TEXT,
            metrics TEXT
          );
        """
        )

        # Optional cache tables
        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS streams_cache(
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            fetched_at TIMESTAMP NOT NULL
          );
        """
        )

        self.conn.execute(
            """
          CREATE TABLE IF NOT EXISTS users_cache(
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            fetched_at TIMESTAMP NOT NULL
          );
        """
        )

        # Record schema version if not exists
        existing_version = self.conn.execute(
            "SELECT version FROM schema_migrations WHERE version = 1"
        ).fetchone()

        if not existing_version:
            self.conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
                [datetime.utcnow()],
            )

    def execute(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> None:
        """Execute a single write operation with transaction wrapping.

        Args:
            sql: SQL statement to execute
            params: Parameters for the SQL statement
        """
        with self._write_lock:
            self.conn.execute("BEGIN")
            try:
                self.conn.execute(sql, params or [])
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def executemany(self, sql: str, seq_params: list[tuple[Any, ...]]) -> None:
        """Execute multiple write operations in a single transaction.

        Args:
            sql: SQL statement to execute
            seq_params: Sequence of parameter tuples
        """
        with self._write_lock:
            self.conn.execute("BEGIN")
            try:
                for params in seq_params:
                    self.conn.execute(sql, params)
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def query(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        """Execute a read query and return results.

        Args:
            sql: SQL query to execute
            params: Parameters for the SQL query

        Returns:
            List of result tuples
        """
        cursor = self.conn.execute(sql, params or [])
        return cursor.fetchall()

    def query_one(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> tuple[Any, ...] | None:
        """Execute a read query and return the first result.

        Args:
            sql: SQL query to execute
            params: Parameters for the SQL query

        Returns:
            First result tuple or None if no results
        """
        cursor = self.conn.execute(sql, params or [])
        return cursor.fetchone()

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_database() -> DatabaseManager:
    """Get or create the global database manager instance.

    Returns:
        Global DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        db_path = os.getenv("ZULIPCHAT_DB_PATH", ".mcp/zulipchat/zulipchat.duckdb")
        _db_manager = DatabaseManager(db_path)
    return _db_manager


def init_database(db_path: str | None = None) -> DatabaseManager:
    """Initialize the global database manager with a specific path.

    Args:
        db_path: Path to the database file, uses default if None

    Returns:
        Initialized DatabaseManager instance
    """
    global _db_manager
    if db_path is None:
        db_path = os.getenv("ZULIPCHAT_DB_PATH", ".mcp/zulipchat/zulipchat.duckdb")
    _db_manager = DatabaseManager(db_path)
    return _db_manager
