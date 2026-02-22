"""DuckDB-backed persistence for ZulipChat MCP state and cache.

Uses short-lived connections for write operations to allow concurrent access
from multiple MCP server instances. Each write operation opens a connection,
executes, and closes it immediately to release the file lock.
"""

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import duckdb


class DatabaseLockedError(Exception):
    """Raised when the database is locked by another process after retries."""

    def __init__(self, db_path: str, original_error: Exception):
        self.db_path = db_path
        self.original_error = original_error
        super().__init__(
            f"Database is locked after max retries: {db_path}. "
            f"Original error: {original_error}"
        )


class DatabaseManager:
    """DuckDB database manager for ZulipChat MCP.

    Uses short-lived connections for write operations to support concurrent
    access from multiple MCP server instances. Write operations acquire the
    lock, execute, and release immediately.
    """

    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "DatabaseManager":
        """Ensure singleton instance within a single process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self, db_path: str, max_retries: int = 5, retry_delay: float = 0.1
    ) -> None:
        """Initialize database manager.

        Args:
            db_path: Path to the DuckDB database file
            max_retries: Maximum number of retry attempts on lock contention
            retry_delay: Base delay between retries (uses exponential backoff)
        """
        # Skip initialization if already initialized
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.db_path = db_path
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._write_lock = threading.RLock()  # Thread safety within process
        self._initialized: bool = False

        dirname = os.path.dirname(db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        # Run migrations using short-lived connection
        self._run_migrations_with_retry()
        self._initialized = True

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """Create a new database connection."""
        return duckdb.connect(self.db_path, config={"access_mode": "READ_WRITE"})

    def _run_migrations_with_retry(self) -> None:
        """Run migrations with retry logic for lock contention."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            conn = None
            try:
                conn = self._connect()
                self._run_migrations(conn)
                return
            except duckdb.IOException as e:
                last_error = e
                if "lock" in str(e).lower() and attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))  # Exponential backoff
                    continue
                raise DatabaseLockedError(self.db_path, e) from e
            finally:
                if conn:
                    conn.close()

        if last_error:
            raise DatabaseLockedError(self.db_path, last_error)

    def _run_migrations(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Run all database migrations idempotently.

        Args:
            conn: Active database connection to use for migrations
        """
        # Create migrations table
        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP
          );
        """
        )

        # Version 1 schema - Core tables for agent tracking and state
        conn.execute(
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

        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS agents(
            agent_id TEXT PRIMARY KEY,
            agent_type TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            metadata TEXT
          );
        """
        )

        conn.execute(
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

        conn.execute(
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

        conn.execute(
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

        # Agent status audit trail (optional)
        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS agent_status(
            status_id TEXT PRIMARY KEY,
            agent_type TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at TIMESTAMP NOT NULL
          );
        """
        )

        # Optional cache tables
        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS streams_cache(
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            fetched_at TIMESTAMP NOT NULL
          );
        """
        )

        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS users_cache(
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            fetched_at TIMESTAMP NOT NULL
          );
        """
        )

        # Record schema version if not exists
        existing_version = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = 1"
        ).fetchone()

        if not existing_version:
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
                [datetime.now(timezone.utc)],
            )

        # Table for agent inbound chat events (from Zulip)
        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS agent_events(
            id TEXT PRIMARY KEY,
            zulip_message_id INTEGER,
            topic TEXT,
            sender_email TEXT,
            content TEXT,
            created_at TIMESTAMP,
            acked BOOLEAN DEFAULT FALSE
          );
        """
        )

        # Persist message listener queue state across restarts
        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS listener_state(
            id INTEGER PRIMARY KEY DEFAULT 1,
            queue_id TEXT,
            last_event_id INTEGER,
            updated_at TIMESTAMP NOT NULL
          );
        """
        )

    def execute(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> None:
        """Execute a single write operation with short-lived connection.

        Opens a connection, executes the statement in a transaction,
        and closes immediately to release the file lock.

        Args:
            sql: SQL statement to execute
            params: Parameters for the SQL statement
        """
        with self._write_lock:  # Thread safety within process
            last_error: Exception | None = None
            for attempt in range(self.max_retries):
                conn = None
                try:
                    conn = self._connect()
                    conn.execute("BEGIN")
                    conn.execute(sql, params or [])
                    conn.execute("COMMIT")
                    return
                except duckdb.IOException as e:
                    last_error = e
                    if "lock" in str(e).lower() and attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2**attempt))
                        continue
                    raise DatabaseLockedError(self.db_path, e) from e
                except Exception:
                    if conn:
                        try:
                            conn.execute("ROLLBACK")
                        except Exception:
                            pass
                    raise
                finally:
                    if conn:
                        conn.close()

            if last_error:
                raise DatabaseLockedError(self.db_path, last_error)

    def executemany(self, sql: str, seq_params: list[tuple[Any, ...]]) -> None:
        """Execute multiple write operations in a single transaction.

        Opens a connection, executes all statements, and closes immediately.

        Args:
            sql: SQL statement to execute
            seq_params: Sequence of parameter tuples
        """
        with self._write_lock:
            last_error: Exception | None = None
            for attempt in range(self.max_retries):
                conn = None
                try:
                    conn = self._connect()
                    conn.execute("BEGIN")
                    for params in seq_params:
                        conn.execute(sql, params)
                    conn.execute("COMMIT")
                    return
                except duckdb.IOException as e:
                    last_error = e
                    if "lock" in str(e).lower() and attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2**attempt))
                        continue
                    raise DatabaseLockedError(self.db_path, e) from e
                except Exception:
                    if conn:
                        try:
                            conn.execute("ROLLBACK")
                        except Exception:
                            pass
                    raise
                finally:
                    if conn:
                        conn.close()

            if last_error:
                raise DatabaseLockedError(self.db_path, last_error)

    def query(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        """Execute a read query and return results.

        Uses short-lived connection with retry for lock contention.

        Args:
            sql: SQL query to execute
            params: Parameters for the SQL query

        Returns:
            List of result tuples
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            conn = None
            try:
                conn = self._connect()
                cursor = conn.execute(sql, params or [])
                return cursor.fetchall()
            except duckdb.IOException as e:
                last_error = e
                if "lock" in str(e).lower() and attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))
                    continue
                raise DatabaseLockedError(self.db_path, e) from e
            finally:
                if conn:
                    conn.close()

        if last_error:
            raise DatabaseLockedError(self.db_path, last_error)
        return []

    def query_one(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> tuple[Any, ...] | None:
        """Execute a read query and return the first result.

        Uses short-lived connection with retry for lock contention.

        Args:
            sql: SQL query to execute
            params: Parameters for the SQL query

        Returns:
            First result tuple or None if no results
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            conn = None
            try:
                conn = self._connect()
                cursor = conn.execute(sql, params or [])
                return cursor.fetchone()
            except duckdb.IOException as e:
                last_error = e
                if "lock" in str(e).lower() and attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))
                    continue
                raise DatabaseLockedError(self.db_path, e) from e
            finally:
                if conn:
                    conn.close()

        if last_error:
            raise DatabaseLockedError(self.db_path, last_error)
        return None

    def query_as_dicts(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read query and return results as dictionaries.

        Uses short-lived connection with retry for lock contention.

        Args:
            sql: SQL query to execute
            params: Parameters for the SQL query

        Returns:
            List of result dictionaries with column names as keys
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            conn = None
            try:
                conn = self._connect()
                cursor = conn.execute(sql, params or [])
                rows = cursor.fetchall()
                if not rows:
                    return []
                desc = cursor.description or []
                columns = [d[0] for d in desc]
                return [dict(zip(columns, row, strict=False)) for row in rows]
            except duckdb.IOException as e:
                last_error = e
                if "lock" in str(e).lower() and attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))
                    continue
                raise DatabaseLockedError(self.db_path, e) from e
            finally:
                if conn:
                    conn.close()

        if last_error:
            raise DatabaseLockedError(self.db_path, last_error)
        return []

    def query_one_as_dict(
        self, sql: str, params: list[Any] | tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        """Execute a read query and return the first result as a dictionary.

        Uses short-lived connection with retry for lock contention.

        Args:
            sql: SQL query to execute
            params: Parameters for the SQL query

        Returns:
            First result as dictionary or None if no results
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            conn = None
            try:
                conn = self._connect()
                cursor = conn.execute(sql, params or [])
                row = cursor.fetchone()
                if row is None:
                    return None
                desc = cursor.description or []
                columns = [d[0] for d in desc]
                return dict(zip(columns, row, strict=False))
            except duckdb.IOException as e:
                last_error = e
                if "lock" in str(e).lower() and attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))
                    continue
                raise DatabaseLockedError(self.db_path, e) from e
            finally:
                if conn:
                    conn.close()

        if last_error:
            raise DatabaseLockedError(self.db_path, last_error)
        return None

    def close(self) -> None:
        """Close the database manager (no-op, connections are short-lived)."""
        pass  # Connections are short-lived, nothing to close

    def __del__(self) -> None:
        """Cleanup (no-op, connections are short-lived)."""
        pass


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
