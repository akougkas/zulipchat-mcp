"""Tests for utils/database.py."""

import pytest
import duckdb
from unittest.mock import MagicMock, patch, call
from src.zulipchat_mcp.utils.database import (
    DatabaseManager,
    DatabaseLockedError,
    init_database,
    get_database,
)


class TestDatabaseManager:
    """Tests for DatabaseManager."""

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
        """Test successful initialization."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)

        assert db.conn is not None
        mock_duckdb.connect.assert_called_with(
            db_path, config={"access_mode": "READ_WRITE"}
        )
        # Check migrations run
        assert db.conn.execute.call_count > 0

    def test_init_lock_retry_success(self, mock_duckdb, tmp_path):
        """Test initialization retries on lock and succeeds."""
        db_path = str(tmp_path / "test.db")
        
        # Fail twice with lock error, then succeed
        lock_error = duckdb.IOException("IO Error: Could not set lock on file")
        conn = MagicMock()
        
        mock_duckdb.connect.side_effect = [lock_error, lock_error, conn]
        
        db = DatabaseManager(db_path, max_retries=3, retry_delay=0.01)
        
        assert db.conn == conn
        assert mock_duckdb.connect.call_count == 3

    def test_init_lock_failure(self, mock_duckdb, tmp_path):
        """Test initialization raises DatabaseLockedError after retries."""
        db_path = str(tmp_path / "test.db")
        lock_error = duckdb.IOException("IO Error: Could not set lock on file")
        
        mock_duckdb.connect.side_effect = lock_error
        
        with pytest.raises(DatabaseLockedError, match="Database is locked"):
            DatabaseManager(db_path, max_retries=3, retry_delay=0.01)
            
        assert mock_duckdb.connect.call_count == 3

    def test_execute_transaction(self, mock_duckdb, tmp_path):
        """Test execute wraps in transaction."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        
        db.conn.reset_mock()
        
        db.execute("INSERT INTO t VALUES (?)", [1])
        
        # Verify transaction calls
        calls = db.conn.execute.call_args_list
        assert calls[0] == call("BEGIN")
        assert calls[1] == call("INSERT INTO t VALUES (?)", [1])
        assert calls[2] == call("COMMIT")

    def test_execute_rollback(self, mock_duckdb, tmp_path):
        """Test execute rolls back on error."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        
        # Create a new mock for this test to avoid side_effect pollution
        db.conn.execute.side_effect = [None, Exception("Fail"), None] # BEGIN, INSERT (fail), ROLLBACK
        
        with pytest.raises(Exception, match="Fail"):
            db.execute("INSERT", [1])
            
        # Verify rollback called (last call)
        # Note: call_args returns the LAST call
        assert db.conn.execute.call_args == call("ROLLBACK")

    def test_executemany(self, mock_duckdb, tmp_path):
        """Test executemany."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        db.conn.reset_mock()
        
        db.executemany("INSERT", [(1,), (2,)])
        
        calls = db.conn.execute.call_args_list
        assert calls[0] == call("BEGIN")
        assert calls[1] == call("INSERT", (1,))
        assert calls[2] == call("INSERT", (2,))
        assert calls[3] == call("COMMIT")

    def test_query(self, mock_duckdb, tmp_path):
        """Test query."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1,)]
        db.conn.execute.return_value = cursor
        
        res = db.query("SELECT *")
        assert res == [(1,)]

    def test_query_one(self, mock_duckdb, tmp_path):
        """Test query_one."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        db.conn.execute.return_value = cursor
        
        res = db.query_one("SELECT *")
        assert res == (1,)

    def test_close(self, mock_duckdb, tmp_path):
        """Test close."""
        db_path = str(tmp_path / "test.db")
        db = DatabaseManager(db_path)
        conn = db.conn
        
        db.close()
        conn.close.assert_called()
        assert db.conn is None

    def test_global_instances(self, mock_duckdb):
        """Test global instance helpers."""
        # reset_singleton fixture handles resetting _db_manager and DatabaseManager._instance
        
        db = init_database(":memory:")
        assert db is not None
        
        db2 = get_database()
        assert db2 is db
        
        # Verify checking calling DatabaseManager() directly also returns the same instance
        db3 = DatabaseManager(":memory:")
        assert db3 is db