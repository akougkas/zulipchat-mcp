"""Tests for core/agent_tracker.py."""

import json
from unittest.mock import patch

import pytest

from src.zulipchat_mcp.core.agent_tracker import AgentTracker


class TestAgentTracker:
    """Tests for AgentTracker."""

    @pytest.fixture
    def mock_cwd(self, tmp_path):
        """Mock current working directory and config paths."""
        # Patch runtime Path.cwd
        with patch(
            "src.zulipchat_mcp.core.agent_tracker.Path.cwd", return_value=tmp_path
        ):
            # Patch class attributes that were evaluated at import time
            with (
                patch(
                    "src.zulipchat_mcp.core.agent_tracker.AgentTracker.CONFIG_DIR",
                    tmp_path / ".mcp",
                ),
                patch(
                    "src.zulipchat_mcp.core.agent_tracker.AgentTracker.AGENT_REGISTRY_FILE",
                    tmp_path / ".mcp" / "agent_registry.json",
                ),
                patch(
                    "src.zulipchat_mcp.core.agent_tracker.AgentTracker.PENDING_RESPONSES_FILE",
                    tmp_path / ".mcp" / "pending_responses.json",
                ),
            ):
                yield tmp_path

    @pytest.fixture
    def tracker(self, mock_cwd):
        return AgentTracker()

    def test_init_creates_config_dir(self, mock_cwd):
        """Test initialization creates .mcp directory."""
        tracker = AgentTracker()
        assert (mock_cwd / ".mcp").exists()
        assert tracker.afk_enabled is False
        assert tracker.session_id is not None

    def test_get_instance_identity(self, tracker, mock_cwd):
        """Test getting instance identity."""
        with patch("socket.gethostname", return_value="testhost"):
            identity = tracker.get_instance_identity()
            assert identity["host"] == "testhost"
            assert identity["cwd"] == str(mock_cwd)
            assert "project" in identity

    def test_register_agent(self, tracker, mock_cwd):
        """Test registering an agent."""
        result = tracker.register_agent("test-agent")

        assert result["status"] == "success"
        assert result["stream"] == "Agents-Channel"
        assert "test-agent" in result["topic"]

        # Verify file written
        registry_file = mock_cwd / ".mcp" / "agent_registry.json"
        assert registry_file.exists()
        data = json.loads(registry_file.read_text())
        assert len(data) == 1
        assert data[0]["agent_type"] == "test-agent"

    def test_update_agent_registry_append(self, tracker, mock_cwd):
        """Test appending to agent registry."""
        registry_file = mock_cwd / ".mcp" / "agent_registry.json"

        # Initial record
        tracker._update_agent_registry({"id": 1})

        # Second record
        tracker._update_agent_registry({"id": 2})

        data = json.loads(registry_file.read_text())
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["id"] == 2

    def test_format_agent_message(self, tracker):
        """Test formatting agent message."""
        msg = tracker.format_agent_message("hello", "test-agent", require_response=True)

        assert msg["status"] == "ready"
        assert msg["stream"] == "Agents-Channel"
        assert msg["content"] == "hello"
        assert msg["response_id"] is not None
        assert "test-agent" in msg["topic"]

    def test_update_registry_handles_error(self, tracker, mock_cwd):
        """Test graceful handling of write errors."""
        # Mock write_text to fail
        with patch("pathlib.Path.write_text", side_effect=OSError("Disk full")):
            # Should not raise exception
            tracker._update_agent_registry({"id": 1})
