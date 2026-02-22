"""Tests for write operations in tools/topic_management.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.topic_management import agents_channel_topic_ops


class TestTopicOperations:
    """Tests for topic management operations."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.get_stream_id.return_value = {"result": "success", "stream_id": 99}
        client.get_messages_raw.return_value = {
            "result": "success",
            "messages": [{"id": 100}],
        }
        client.edit_message.return_value = {"result": "success"}
        client.delete_topic.return_value = {"result": "success"}
        client.mute_topic.return_value = {"result": "success"}
        client.unmute_topic.return_value = {"result": "success"}
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch(
                "src.zulipchat_mcp.tools.topic_management.get_config_manager"
            ) as mock_config_cls,
            patch(
                "src.zulipchat_mcp.tools.topic_management.is_unsafe_mode"
            ) as mock_unsafe,
            patch(
                "src.zulipchat_mcp.tools.topic_management.get_bot_client"
            ) as mock_get_bot_client,
        ):
            # Setup ConfigManager
            mock_config = mock_config_cls.return_value
            mock_config.has_bot_credentials.return_value = True

            # Setup ZulipClientWrapper
            mock_get_bot_client.return_value = mock_client

            # Default safe mode
            mock_unsafe.return_value = False

            yield {"config": mock_config, "client": mock_client, "unsafe": mock_unsafe}

    @pytest.mark.asyncio
    async def test_move_topic_success(self, mock_deps):
        """Test moving a topic successfully."""
        result = await agents_channel_topic_ops("move", "source", "target")
        assert result["status"] == "success"
        assert result["operation"] == "move"

        # Verify call chain
        client = mock_deps["client"]
        client.get_stream_id.assert_called_with("Agents-Channel")
        client.edit_message.assert_called_with(
            message_id=100, topic="target", propagate_mode="change_all"
        )

    @pytest.mark.asyncio
    async def test_move_without_target(self, mock_deps):
        """Test moving topic without target topic."""
        result = await agents_channel_topic_ops("move", "source")
        assert result["status"] == "error"
        assert "target_topic required" in result["error"]

    @pytest.mark.asyncio
    async def test_move_empty_topic(self, mock_deps):
        """Test moving a topic with no messages (can't move if no anchor message)."""
        mock_deps["client"].get_messages_raw.return_value = {
            "result": "success",
            "messages": [],
        }
        result = await agents_channel_topic_ops("move", "source", "target")
        assert result["status"] == "error"
        assert "No messages found" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_requires_unsafe_mode(self, mock_deps):
        """Test delete operation requires unsafe mode."""
        # unsafe is False by default in fixture
        result = await agents_channel_topic_ops("delete", "source")
        assert result["status"] == "error"
        assert "requires --unsafe mode" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_topic_success_unsafe(self, mock_deps):
        """Test delete operation in unsafe mode."""
        mock_deps["unsafe"].return_value = True
        result = await agents_channel_topic_ops("delete", "source")
        assert result["status"] == "success"
        assert result["operation"] == "delete"

        mock_deps["client"].delete_topic.assert_called_with(99, "source")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_topic(self, mock_deps):
        """Test deleting nonexistent topic (backend error)."""
        mock_deps["unsafe"].return_value = True
        mock_deps["client"].delete_topic.return_value = {
            "result": "error",
            "msg": "Topic not found",
        }

        result = await agents_channel_topic_ops("delete", "ghost")
        assert result["status"] == "error"
        assert "Topic not found" in result["error"]

    @pytest.mark.asyncio
    async def test_requires_bot_credentials(self, mock_deps):
        """Test that operation is rejected without bot credentials."""
        mock_deps["config"].has_bot_credentials.return_value = False

        result = await agents_channel_topic_ops("move", "source", "target")
        assert result["status"] == "error"
        assert "Bot credentials required" in result["error"]

    @pytest.mark.asyncio
    async def test_only_agents_channel_allowed(self, mock_deps):
        """Test rejection if Agents-Channel is not found (e.g. wrong env)."""
        mock_deps["client"].get_stream_id.return_value = {
            "result": "error",
            "msg": "Stream not found",
        }

        result = await agents_channel_topic_ops("move", "source", "target")
        assert result["status"] == "error"
        assert "Agents-Channel not found" in result["error"]

    @pytest.mark.asyncio
    async def test_mute_unmute(self, mock_deps):
        """Test mute/unmute operations (which don't require unsafe mode but require bot)."""
        # Mute
        res_mute = await agents_channel_topic_ops("mute", "noisy")
        assert res_mute["status"] == "success"
        mock_deps["client"].mute_topic.assert_called_with(99, "noisy")

        # Unmute
        res_unmute = await agents_channel_topic_ops("unmute", "noisy")
        assert res_unmute["status"] == "success"
        mock_deps["client"].unmute_topic.assert_called_with(99, "noisy")
