"""Tests for utils/database.py - short-lived connection pattern."""

from unittest.mock import MagicMock, call, patch

import duckdb
import pytest

from src.zulipchat_mcp.utils.database import (
    DatabaseLockedError,
    DatabaseManager,
    get_database,
    init_database,
)


class TestDatabaseManager:
    """Tests for DatabaseManager with short-lived connections."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        DatabaseManager._instance = None
        # Also reset the global variable in the module
        with patch("src.zulipchat_mcp.utils.database._db_manager", None):
            yield
        DatabaseManager._instance = None

    @pytest.fixture
    def mock_duckdb(self):
        with patch("src.zulipchat_mcp.utils.database.duckdb") as mock:
            conn = MagicMock()
            mock.connect.return_value = conn
            mock.IOException = duckdb.IOException
            yield mock

    def test_init_success(self, mock_duckdb, tmp_path):
        """Test successful initialization with short-lived connection for migrations."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        assert db._initialized is True
        assert db.db_path == db_path
        # Connection was opened for migrations and closed
        mock_duckdb.connect.assert_called()

    def test_init_lock_retry_success(self, mock_duckdb, tmp_path):
        """Test initialization retries on lock and succeeds."""
        db_path = str(tmp_path / "test.db")

        # Fail twice with lock error, then succeed
        lock_error = duckdb.IOException("IO Error: Could not set lock on file")
        conn = MagicMock()

        mock_duckdb.connect.side_effect = [lock_error, lock_error, conn]

        db = DatabaseManager(db_path, max_retries=3, retry_delay=0.01)

        assert db._initialized is True
        assert mock_duckdb.connect.call_count == 3

    def test_init_lock_failure(self, mock_duckdb, tmp_path):
        """Test initialization raises DatabaseLockedError after retries."""
        db_path = str(tmp_path / "test.db")
        lock_error = duckdb.IOException("IO Error: Could not set lock on file")

        mock_duckdb.connect.side_effect = lock_error

        with pytest.raises(DatabaseLockedError, match="Database is locked"):
            DatabaseManager(db_path, max_retries=3, retry_delay=0.01)

        assert mock_duckdb.connect.call_count == 3

    def test_execute_opens_closes_connection(self, mock_duckdb, tmp_path):
        """Test execute opens and closes connection for each operation."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        # Reset mock to clear init calls
        mock_duckdb.connect.reset_mock()
        conn = MagicMock()
        mock_duckdb.connect.return_value = conn

        db.execute("INSERT INTO t VALUES (?)", [1])

        # Verify connection opened
        mock_duckdb.connect.assert_called_once()
        # Verify transaction calls
        calls = conn.execute.call_args_list
        assert call("BEGIN") in calls
        assert call("INSERT INTO t VALUES (?)", [1]) in calls
        assert call("COMMIT") in calls
        # Verify connection closed
        conn.close.assert_called_once()

    def test_execute_retry_on_lock(self, mock_duckdb, tmp_path):
        """Test execute retries on lock contention."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path, max_retries=3, retry_delay=0.01)

        mock_duckdb.connect.reset_mock()

        # First two connections fail with lock, third succeeds
        lock_error = duckdb.IOException("IO Error: lock")
        conn_success = MagicMock()
        mock_duckdb.connect.side_effect = [lock_error, lock_error, conn_success]

        db.execute("INSERT", [1])

        assert mock_duckdb.connect.call_count == 3
        conn_success.close.assert_called_once()

    def test_execute_rollback_on_error(self, mock_duckdb, tmp_path):
        """Test execute rolls back on error."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        mock_duckdb.connect.reset_mock()
        conn = MagicMock()
        mock_duckdb.connect.return_value = conn

        # Simulate error on the INSERT
        conn.execute.side_effect = [
            None,  # BEGIN
            Exception("Fail"),  # INSERT fails
            None,  # ROLLBACK
        ]

        with pytest.raises(Exception, match="Fail"):
            db.execute("INSERT", [1])

        # Verify rollback was called
        assert call("ROLLBACK") in conn.execute.call_args_list
        conn.close.assert_called()

    def test_executemany(self, mock_duckdb, tmp_path):
        """Test executemany uses short-lived connection."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        mock_duckdb.connect.reset_mock()
        conn = MagicMock()
        mock_duckdb.connect.return_value = conn

        db.executemany("INSERT", [(1,), (2,)])

        calls = conn.execute.call_args_list
        assert call("BEGIN") in calls
        assert call("INSERT", (1,)) in calls
        assert call("INSERT", (2,)) in calls
        assert call("COMMIT") in calls
        conn.close.assert_called_once()

    def test_query(self, mock_duckdb, tmp_path):
        """Test query uses short-lived connection."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        mock_duckdb.connect.reset_mock()
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1,)]
        conn.execute.return_value = cursor
        mock_duckdb.connect.return_value = conn

        res = db.query("SELECT *")

        assert res == [(1,)]
        conn.close.assert_called_once()

    def test_query_one(self, mock_duckdb, tmp_path):
        """Test query_one uses short-lived connection."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        mock_duckdb.connect.reset_mock()
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        conn.execute.return_value = cursor
        mock_duckdb.connect.return_value = conn

        res = db.query_one("SELECT *")

        assert res == (1,)
        conn.close.assert_called_once()

    def test_query_as_dicts(self, mock_duckdb, tmp_path):
        """Test query_as_dicts returns list of dicts."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        mock_duckdb.connect.reset_mock()
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1, "a"), (2, "b")]
        cursor.description = [("id",), ("name",)]
        conn.execute.return_value = cursor
        mock_duckdb.connect.return_value = conn

        res = db.query_as_dicts("SELECT *")

        assert res == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        conn.close.assert_called_once()

    def test_query_one_as_dict(self, mock_duckdb, tmp_path):
        """Test query_one_as_dict returns single dict."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        mock_duckdb.connect.reset_mock()
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (1, "a")
        cursor.description = [("id",), ("name",)]
        conn.execute.return_value = cursor
        mock_duckdb.connect.return_value = conn

        res = db.query_one_as_dict("SELECT *")

        assert res == {"id": 1, "name": "a"}
        conn.close.assert_called_once()

    def test_close_is_noop(self, mock_duckdb, tmp_path):
        """Test close is a no-op since connections are short-lived."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        # close should not raise and should be a no-op
        db.close()
        assert db._initialized is True

    def test_global_instances(self, mock_duckdb):
        """Test global instance helpers."""
        db = init_database(":memory:")
        assert db is not None

        db2 = get_database()
        assert db2 is db

        # Verify calling DatabaseManager() directly also returns the same instance
        db3 = DatabaseManager(":memory:")
        assert db3 is db
