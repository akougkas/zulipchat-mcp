"""Tests for the session-oriented agent tools."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.agents import (
    agent_message,
    close_agent_session,
    complete_task,
    ensure_agent_session,
    list_instances,
    list_sessions,
    manage_task,
    poll_agent_events,
    register_agent,
    request_user_input,
    send_agent_status,
    start_task,
    update_task_progress,
    wait_for_response,
)


class TestAgentTools:
    """Tests for session-aware agent tools."""

    @pytest.fixture(autouse=True)
    def mock_ensure_listener(self):
        with patch("src.zulipchat_mcp.tools.agents.ensure_listener"):
            yield

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
            "created": True,
            "session": {
                "session_id": "sess-1",
                "agent_id": "agent-1",
                "external_session_id": "cc-123",
                "stream_name": "Agents-Channel",
                "topic_name": "Agents/Session/project/claude/cc-123",
                "owner_email": "owner@example.com",
                "project_name": "project",
                "status": "active",
            },
        }
        coordinator.send_session_message.return_value = {
            "status": "success",
            "session_id": "sess-1",
            "message_id": 100,
            "category": "message",
        }
        coordinator.create_request.return_value = {
            "status": "success",
            "request_id": "req-1",
            "session_id": "sess-1",
            "message_id": 101,
        }
        coordinator.wait_for_request_async = AsyncMock(
            return_value={
                "status": "success",
                "request_status": "answered",
                "response": "approve",
                "responded_at": "2026-03-21T10:00:00+00:00",
            }
        )
        with patch(
            "src.zulipchat_mcp.tools.agents._get_coordinator",
            return_value=coordinator,
        ):
            yield coordinator

    @pytest.fixture
    def mock_db(self):
        with patch("src.zulipchat_mcp.tools.agents.DatabaseManager") as mock_db_cls:
            db_instance = MagicMock()
            mock_db_cls.return_value = db_instance
            yield db_instance

    def test_register_agent(self, mock_coordinator):
        result = register_agent(agent_name="claude", agent_type="claude-code")
        assert result["status"] == "success"
        assert result["agent_id"] == "agent-1"
        assert result["stream"] == "Agents-Channel"
        mock_coordinator.register_agent.assert_called_once()

    def test_ensure_agent_session(self, mock_coordinator):
        result = ensure_agent_session(
            "agent-1",
            external_session_id="cc-123",
            project_dir="/tmp/project",
        )
        assert result["status"] == "success"
        assert result["session_id"] == "sess-1"
        assert result["created"] is True
        mock_coordinator.ensure_session.assert_called_once()

    def test_agent_message(self, mock_coordinator):
        result = agent_message("sess-1", "hello", category="started")
        assert result["status"] == "success"
        mock_coordinator.send_session_message.assert_called_once_with(
            session_id="sess-1",
            content="hello",
            category="started",
            request_id=None,
            metadata=None,
        )

    @pytest.mark.asyncio
    async def test_wait_for_response_success(self, mock_coordinator):
        result = await wait_for_response("req-1", timeout_seconds=5)
        assert result["status"] == "success"
        assert result["response"] == "approve"
        mock_coordinator.wait_for_request_async.assert_called_once_with(
            "req-1", timeout_seconds=5
        )

    def test_send_agent_status(self, mock_db):
        mock_db.get_agent_profile.return_value = {"agent_type": "claude-code"}
        result = send_agent_status("agent-1", "working")
        assert result["status"] == "success"
        mock_db.create_agent_status.assert_called_once()

    def test_request_user_input(self, mock_coordinator):
        result = request_user_input(
            "sess-1",
            "Deploy now?",
            options=["approve", "deny"],
            request_type="approval",
        )
        assert result["status"] == "success"
        assert result["request_id"] == "req-1"
        mock_coordinator.create_request.assert_called_once()

    def test_start_task(self, mock_db):
        result = start_task("agent-1", "Task")
        assert result["status"] == "success"
        mock_db.execute.assert_called()

    def test_update_task_progress(self, mock_db):
        result = update_task_progress("task-1", 50, "working")
        assert result["status"] == "success"
        mock_db.execute.assert_called()

    def test_complete_task(self, mock_db):
        result = complete_task("task-1")
        assert result["status"] == "success"
        mock_db.execute.assert_called()

    def test_list_sessions(self, mock_db):
        mock_db.list_agent_sessions.return_value = [
            {
                "session_id": "sess-1",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "ended_at": None,
            }
        ]
        result = list_sessions()
        assert result["status"] == "success"
        assert len(result["sessions"]) == 1

    def test_list_instances_alias(self, mock_db):
        mock_db.list_agent_sessions.return_value = [{"session_id": "sess-1"}]
        result = list_instances()
        assert result["status"] == "success"
        assert result["instances"][0]["session_id"] == "sess-1"

    def test_close_agent_session(self, mock_db, mock_coordinator):
        mock_db.get_agent_session.return_value = {
            "session_id": "sess-1",
            "agent_id": "agent-1",
            "stream_name": "Agents-Channel",
            "topic_name": "Agents/Session/project/claude/cc-123",
        }
        result = close_agent_session("sess-1", summary="Done")
        assert result["status"] == "success"
        mock_db.update_agent_session.assert_called_once()
        mock_coordinator.send_session_message.assert_called_once()

    def test_poll_agent_events(self, mock_db):
        mock_db.get_unacked_session_events.return_value = [
            {"id": "evt-1", "content": "hi"}
        ]
        result = poll_agent_events(session_id="sess-1")
        assert result["status"] == "success"
        assert result["count"] == 1
        mock_db.ack_session_events.assert_called_once_with(["evt-1"])

    def test_manage_task_dispatch(self):
        with patch("src.zulipchat_mcp.tools.agents.start_task") as mock_start:
            mock_start.return_value = {"status": "success"}
            result = manage_task(action="start", agent_id="agent-1", name="Task")
            assert result["status"] == "success"

        with patch(
            "src.zulipchat_mcp.tools.agents.update_task_progress"
        ) as mock_update:
            mock_update.return_value = {"status": "success"}
            result = manage_task(action="update", task_id="task-1", progress=25)
            assert result["status"] == "success"

        with patch("src.zulipchat_mcp.tools.agents.complete_task") as mock_complete:
            mock_complete.return_value = {"status": "success"}
            result = manage_task(action="complete", task_id="task-1")
            assert result["status"] == "success"
