"""Tests for utils/database_manager.py."""

import pytest
from unittest.mock import MagicMock, patch, ANY
from src.zulipchat_mcp.utils.database_manager import DatabaseManager


class TestDatabaseManagerWrapper:
    """Tests for the high-level DatabaseManager wrapper."""

    @pytest.fixture
    def mock_db(self):
        with patch("src.zulipchat_mcp.utils.database_manager.get_database") as mock_get:
            db_instance = MagicMock()
            mock_get.return_value = db_instance
            yield db_instance

    def test_init(self, mock_db):
        """Test initialization."""
        manager = DatabaseManager()
        assert manager._db == mock_db
        assert manager.conn == mock_db.conn

    def test_create_agent_instance(self, mock_db):
        """Test create_agent_instance."""
        manager = DatabaseManager()
        
        result = manager.create_agent_instance(
            "agent1", "type", "proj", instance_id="inst1"
        )
        assert result["status"] == "success"
        mock_db.execute.assert_called()
        sql = mock_db.execute.call_args[0][0]
        assert "INSERT INTO agent_instances" in sql

    def test_get_agent_instance(self, mock_db):
        """Test get_agent_instance."""
        manager = DatabaseManager()
        
        # Setup mock cursor
        cursor = MagicMock()
        cursor.fetchone.return_value = ("inst1", "agent1")
        cursor.description = [("instance_id",), ("agent_id",)]
        manager.conn.execute.return_value = cursor
        
        result = manager.get_agent_instance("agent1")
        assert result["instance_id"] == "inst1"
        manager.conn.execute.assert_called()

    def test_create_input_request(self, mock_db):
        """Test create_input_request."""
        manager = DatabaseManager()
        result = manager.create_input_request("req1", "ag1", "Q")
        assert result["status"] == "success"
        mock_db.execute.assert_called()

    def test_get_input_request(self, mock_db):
        """Test get_input_request."""
        manager = DatabaseManager()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("req1", "Q")
        cursor.description = [("request_id",), ("question",)]
        manager.conn.execute.return_value = cursor
        
        result = manager.get_input_request("req1")
        assert result["request_id"] == "req1"

    def test_update_input_request(self, mock_db):
        """Test update_input_request."""
        manager = DatabaseManager()
        manager.update_input_request("req1", status="done")
        mock_db.execute.assert_called()
        sql = mock_db.execute.call_args[0][0]
        assert "UPDATE user_input_requests" in sql

    def test_create_task(self, mock_db):
        """Test create_task."""
        manager = DatabaseManager()
        manager.create_task("t1", "a1", "name")
        mock_db.execute.assert_called()

    def test_update_task(self, mock_db):
        """Test update_task."""
        manager = DatabaseManager()
        manager.update_task("t1", progress=50)
        mock_db.execute.assert_called()

    def test_afk_state(self, mock_db):
        """Test set/get afk_state."""
        manager = DatabaseManager()
        
        # Set
        manager.set_afk_state(True)
        mock_db.execute.assert_called() # Actually called twice (DELETE then INSERT)
        
        # Get
        cursor = MagicMock()
        cursor.fetchone.return_value = (1, True)
        cursor.description = [("id",), ("is_afk",)]
        manager.conn.execute.return_value = cursor
        
        state = manager.get_afk_state()
        assert state["is_afk"] is True

    def test_agent_status(self, mock_db):
        """Test create_agent_status."""
        manager = DatabaseManager()
        manager.create_agent_status("s1", "type", "idle")
        mock_db.execute.assert_called()

    def test_agent_events(self, mock_db):
        """Test event operations."""
        manager = DatabaseManager()
        
        # Create
        manager.create_agent_event("e1", 1, "topic", "sender", "content")
        mock_db.execute.assert_called()
        
        # Get unacked
        cursor = MagicMock()
        cursor.fetchall.return_value = [("e1",)]
        cursor.description = [("id",)]
        manager.conn.execute.return_value = cursor
        
        events = manager.get_unacked_events()
        assert len(events) == 1
        assert events[0]["id"] == "e1"
        
        # Ack
        manager.ack_events(["e1"])
        mock_db.execute.assert_called()
