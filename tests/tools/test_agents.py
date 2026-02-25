"""Tests for tools/agents.py."""

from unittest.mock import ANY, MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.agents import (
    agent_message,
    complete_task,
    disable_afk_mode,
    enable_afk_mode,
    get_afk_status,
    list_instances,
    poll_agent_events,
    register_agent,
    request_user_input,
    send_agent_status,
    start_task,
    update_task_progress,
    wait_for_response,
)


class TestAgentTools:
    """Tests for agent tools."""

    @pytest.fixture(autouse=True)
    def mock_ensure_listener(self):
        with patch("src.zulipchat_mcp.tools.agents.ensure_listener"):
            yield

    @pytest.fixture
    def mock_db(self):
        with patch("src.zulipchat_mcp.tools.agents.DatabaseManager") as mock_db_cls:
            db_instance = MagicMock()
            mock_db_cls.return_value = db_instance
            yield db_instance

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.get_streams.return_value = {
            "result": "success",
            "streams": [{"name": "Agents-Channel"}],
        }
        client.send_message.return_value = {"result": "success", "id": 100}

        with patch(
            "src.zulipchat_mcp.tools.agents._get_client_bot", return_value=client
        ):
            yield client

    @pytest.fixture
    def mock_tracker(self):
        tracker = MagicMock()
        tracker.format_agent_message.return_value = {
            "status": "ready",
            "stream": "Agents-Channel",
            "content": "msg",
            "topic": "topic",
            "response_id": "resp_id",
        }
        with patch("src.zulipchat_mcp.tools.agents._tracker", tracker):
            yield tracker

    def test_register_agent(self, mock_db, mock_client):
        """Test register_agent."""
        result = register_agent("test-agent")
        assert result["status"] == "success"
        assert result["agent_type"] == "test-agent"
        mock_db.execute.assert_called()  # Should call execute multiple times

    def test_register_agent_stream_fallback(self, mock_db, mock_client):
        """Test register_agent uses fallback stream when preferred not available."""
        # No Agents-Channel, but sandbox exists
        mock_client.get_streams.return_value = {
            "result": "success",
            "streams": [{"name": "sandbox", "invite_only": False}],
        }
        # Reset cached stream to force re-discovery
        import src.zulipchat_mcp.tools.agents as agents_module

        agents_module._agent_stream = None

        result = register_agent()
        assert result["status"] == "success"
        assert result["stream"] == "sandbox"  # Falls back to available stream

    def test_agent_message_afk_enabled(self, mock_db, mock_client, mock_tracker):
        """Test agent_message when AFK is enabled."""
        mock_db.get_afk_state.return_value = {"is_afk": True}

        result = agent_message("hello")

        assert result["status"] == "success"
        mock_client.send_message.assert_called()

    def test_agent_message_afk_disabled(self, mock_db, mock_client, mock_tracker):
        """Test agent_message skipped when AFK is disabled."""
        mock_db.get_afk_state.return_value = {"is_afk": False}

        # Override dev notify check? It checks env.
        with patch.dict("os.environ", {"ZULIP_DEV_NOTIFY": "0"}):
            result = agent_message("hello")
            assert result["status"] == "skipped"
            mock_client.send_message.assert_not_called()

    def test_wait_for_response_success(self, mock_db):
        """Test wait_for_response success."""
        mock_db.get_input_request.return_value = {
            "status": "answered",
            "response": "yes",
            "responded_at": "2023-01-01",
        }

        result = wait_for_response("req_id")
        assert result["status"] == "success"
        assert result["response"] == "yes"

    def test_send_agent_status(self, mock_db):
        """Test send_agent_status."""
        result = send_agent_status("agent", "working")
        assert result["status"] == "success"
        mock_db.create_agent_status.assert_called()

    def test_request_user_input(self, mock_db, mock_client):
        """Test request_user_input."""
        mock_db.get_afk_state.return_value = {"is_afk": True}
        mock_db.get_agent_instance.return_value = {"project_dir": "/tmp"}
        mock_db.query_one.return_value = [None]  # No metadata

        result = request_user_input("agent_id", "Q?")
        assert result["status"] == "success"
        mock_db.create_input_request.assert_called()
        mock_client.send_message.assert_called()

    def test_start_task(self, mock_db):
        """Test start_task."""
        result = start_task("agent", "task")
        assert result["status"] == "success"
        mock_db.execute.assert_called()

    def test_update_task_progress(self, mock_db):
        """Test update_task_progress."""
        result = update_task_progress("tid", 50)
        assert result["status"] == "success"
        mock_db.execute.assert_called()

    def test_complete_task(self, mock_db):
        """Test complete_task."""
        result = complete_task("tid")
        assert result["status"] == "success"
        mock_db.execute.assert_called()

    def test_list_instances(self, mock_db):
        """Test list_instances."""
        mock_db.query.return_value = [
            ("inst1", "ag1", "type", "sess", "dir", "host", None)
        ]
        result = list_instances()
        assert result["status"] == "success"
        assert len(result["instances"]) == 1

    def test_afk_mode(self, mock_db):
        """Test enable/disable/get AFK."""
        # Enable
        res = enable_afk_mode()
        assert res["status"] == "success"
        mock_db.set_afk_state.assert_called_with(enabled=True, reason=ANY, hours=8)

        # Disable
        res = disable_afk_mode()
        assert res["status"] == "success"
        mock_db.set_afk_state.assert_called_with(enabled=False, reason="", hours=0)

        # Get
        mock_db.get_afk_state.return_value = {"is_afk": True}
        res = get_afk_status()
        assert res["status"] == "success"
        assert res["afk_state"]["enabled"] is True

    def test_poll_agent_events(self, mock_db):
        """Test poll_agent_events."""
        mock_db.get_unacked_events.return_value = [{"id": 1, "content": "msg"}]

        result = poll_agent_events()
        assert result["status"] == "success"
        assert len(result["events"]) == 1
        mock_db.ack_events.assert_called_with([1])
