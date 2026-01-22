"""Tests for write operations in tools/agents.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.agents import (
    complete_task,
    disable_afk_mode,
    enable_afk_mode,
    register_agent,
    start_task,
    update_task_progress,
)


class TestAgentOperations:
    """Tests for agent/task tracking operations."""

    @pytest.fixture
    def mock_db(self):
        """Mock DatabaseManager."""
        db = MagicMock()
        return db

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.get_streams.return_value = {
            "result": "success",
            "streams": [{"name": "Agents-Channel"}],
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_db, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.agents.DatabaseManager") as mock_db_cls,
            patch("src.zulipchat_mcp.tools.agents.get_client") as mock_get_client:

            mock_db_cls.return_value = mock_db
            mock_get_client.return_value = mock_client

            # Reset global client cache for clean tests
            with patch("src.zulipchat_mcp.tools.agents._client", None):
                yield {"db": mock_db, "client": mock_client}

    @pytest.mark.asyncio
    async def test_register_agent_success(self, mock_deps):
        """Test registering an agent."""
        result = register_agent("test-agent")
        assert result["status"] == "success"
        assert result["agent_type"] == "test-agent"
        assert "agent_id" in result

        # Verify DB calls: 3 executes (agent, instance, afk)
        assert mock_deps["db"].execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_register_duplicate_agent(self, mock_deps):
        """Test registering agent (always generates new ID, so duplicates aren't an issue logically)."""
        res1 = register_agent("agent1")
        res2 = register_agent("agent1")
        assert res1["agent_id"] != res2["agent_id"]
        assert res1["status"] == "success"
        assert res2["status"] == "success"

    @pytest.mark.asyncio
    async def test_register_with_invalid_type(self, mock_deps):
        """Test registering with unusual type string."""
        result = register_agent(agent_type="")
        assert result["status"] == "success"
        # Code allows empty string

    @pytest.mark.asyncio
    async def test_start_task_success(self, mock_deps):
        """Test starting a task."""
        result = start_task("agent-123", "Task 1", "Description")
        assert result["status"] == "success"
        assert "task_id" in result

        mock_deps["db"].execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_progress_valid_range(self, mock_deps):
        """Test updating progress."""
        result = update_task_progress("task-1", 50, "working")
        assert result["status"] == "success"

        args = mock_deps["db"].execute.call_args
        assert args[0][0].startswith("UPDATE tasks SET progress = ?")
        assert 50 in args[0][1]

    @pytest.mark.asyncio
    async def test_update_progress_over_100(self, mock_deps):
        """Test updating progress > 100 (should pass, DB stores int)."""
        result = update_task_progress("task-1", 110)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_update_progress_negative(self, mock_deps):
        """Test updating progress < 0."""
        result = update_task_progress("task-1", -10)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_complete_task_success(self, mock_deps):
        """Test completing a task."""
        result = complete_task("task-1", "Done", "stats")
        assert result["status"] == "success"

        mock_deps["db"].execute.assert_called()
        args = mock_deps["db"].execute.call_args
        assert "completed" in args[0][1]
        assert 100 in args[0][1]

    @pytest.mark.asyncio
    async def test_complete_nonexistent_task(self, mock_deps):
        """Test completing nonexistent task (DB operation succeeds with 0 updates)."""
        result = complete_task("ghost-task")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_enable_afk_mode(self, mock_deps):
        """Test enabling AFK mode."""
        result = enable_afk_mode(hours=4, reason="Lunch")
        assert result["status"] == "success"

        mock_deps["db"].set_afk_state.assert_called_with(
            enabled=True, reason="Lunch", hours=4
        )

    @pytest.mark.asyncio
    async def test_disable_afk_mode(self, mock_deps):
        """Test disabling AFK mode."""
        result = disable_afk_mode()
        assert result["status"] == "success"

        mock_deps["db"].set_afk_state.assert_called_with(
            enabled=False, reason="", hours=0
        )

    @pytest.mark.asyncio
    async def test_afk_hours_negative(self, mock_deps):
        """Test AFK hours negative."""
        result = enable_afk_mode(hours=-1)
        assert result["status"] == "success"  # Tool passes it through

    @pytest.mark.asyncio
    async def test_afk_hours_very_large(self, mock_deps):
        """Test AFK hours large."""
        result = enable_afk_mode(hours=999999)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_database_lock_retry(self, mock_deps):
        """Test database error handling."""
        mock_deps["db"].execute.side_effect = Exception("Database is locked")
        result = start_task("agent", "task")
        assert result["status"] == "error"
        assert "Database is locked" in result["error"]
