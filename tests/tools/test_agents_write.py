"""Focused write-path tests for session-oriented agent tools."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.agents import (
    close_agent_session,
    ensure_agent_session,
    register_agent,
    start_task,
    update_task_progress,
)


class TestAgentOperations:
    """Tests for agent/session/task write operations."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.update_agent_session.return_value = {"status": "success"}
        return db

    @pytest.fixture
    def mock_coordinator(self):
        coordinator = MagicMock()
        coordinator.register_agent.return_value = {
            "status": "success",
            "agent": {
                "agent_id": "agent-1",
                "agent_name": "claude",
                "agent_type": "claude-code",
                "owner_email": "owner@example.com",
                "stream_name": "Agents-Channel",
                "topic_prefix": "Agents/Session",
            },
        }
        coordinator.ensure_session.return_value = {
            "status": "success",
            "created": False,
            "session": {
                "session_id": "sess-1",
                "agent_id": "agent-1",
                "stream_name": "Agents-Channel",
                "topic_name": "Agents/Session/project/claude/cc-123",
                "owner_email": "owner@example.com",
                "project_name": "project",
                "status": "active",
            },
        }
        coordinator.send_session_message.return_value = {"status": "success"}
        return coordinator

    @pytest.fixture
    def mock_deps(self, mock_db, mock_coordinator):
        with (
            patch("src.zulipchat_mcp.tools.agents.DatabaseManager") as mock_db_cls,
            patch(
                "src.zulipchat_mcp.tools.agents._get_coordinator",
                return_value=mock_coordinator,
            ),
        ):
            mock_db_cls.return_value = mock_db
            yield {"db": mock_db, "coordinator": mock_coordinator}

    @pytest.mark.asyncio
    async def test_register_agent_is_stable(self, mock_deps):
        result = register_agent(agent_name="claude", agent_type="claude-code")
        assert result["status"] == "success"
        assert result["agent_id"] == "agent-1"
        mock_deps["coordinator"].register_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_session_returns_existing_binding(self, mock_deps):
        result = ensure_agent_session("agent-1", project_dir="/tmp/project")
        assert result["status"] == "success"
        assert result["created"] is False

    @pytest.mark.asyncio
    async def test_start_task_success(self, mock_deps):
        result = start_task("agent-1", "Task 1", "Description")
        assert result["status"] == "success"
        mock_deps["db"].execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_progress_valid_range(self, mock_deps):
        result = update_task_progress("task-1", 50, "working")
        assert result["status"] == "success"
        sql, params = mock_deps["db"].execute.call_args[0]
        assert sql.startswith("UPDATE tasks SET progress = ?")
        assert 50 in params

    @pytest.mark.asyncio
    async def test_update_progress_negative(self, mock_deps):
        result = update_task_progress("task-1", -10)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_close_session_success(self, mock_deps):
        mock_deps["db"].get_agent_session.return_value = {
            "session_id": "sess-1",
            "agent_id": "agent-1",
            "stream_name": "Agents-Channel",
            "topic_name": "Agents/Session/project/claude/cc-123",
        }
        result = close_agent_session("sess-1", summary="Done")
        assert result["status"] == "success"
        mock_deps["db"].update_agent_session.assert_called_once()
        mock_deps["coordinator"].send_session_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_lock_retry(self, mock_deps):
        mock_deps["db"].execute.side_effect = Exception("Database is locked")
        result = start_task("agent", "task")
        assert result["status"] == "error"
        assert "Database is locked" in result["error"]
