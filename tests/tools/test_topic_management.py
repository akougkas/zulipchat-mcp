"""Tests for tools/topic_management.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.topic_management import (
    agents_channel_topic_ops,
    get_stream_topics,
)


class TestTopicManagementTools:
    """Tests for topic management tools."""

    @pytest.fixture
    def mock_deps(self):
        with (
            patch(
                "src.zulipchat_mcp.tools.topic_management.get_config_manager"
            ) as mock_config,
            patch(
                "src.zulipchat_mcp.tools.topic_management.is_unsafe_mode"
            ) as mock_unsafe,
        ):

            client = MagicMock()
            mock_get_client.return_value = client
            mock_config_instance = MagicMock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.has_bot_credentials.return_value = True

            yield client, mock_unsafe, mock_config_instance

    @pytest.mark.asyncio
    async def test_get_stream_topics(self, mock_deps):
        """Test get_stream_topics."""
        client, _, _ = mock_deps
        client.get_stream_topics.return_value = {
            "result": "success",
            "topics": [{"name": "t1"}],
        }

        result = await get_stream_topics(1)
        assert result["status"] == "success"
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_agents_channel_topic_ops_no_bot(self, mock_deps):
        """Test missing bot credentials."""
        _, _, config = mock_deps
        config.has_bot_credentials.return_value = False

        result = await agents_channel_topic_ops("move", "src")
        assert result["status"] == "error"
        assert "Bot credentials required" in result["error"]

    @pytest.mark.asyncio
    async def test_agents_channel_topic_ops_missing_channel(self, mock_deps):
        """Test missing Agents-Channel (Bug Regression)."""
        client, _, _ = mock_deps
        client.get_stream_id.return_value = {"result": "error"}

        result = await agents_channel_topic_ops("move", "src")
        assert result["status"] == "error"
        assert "Agents-Channel not found" in result["error"]

    @pytest.mark.asyncio
    async def test_agents_channel_topic_ops_move(self, mock_deps):
        """Test move topic."""
        client, _, _ = mock_deps
        client.get_stream_id.return_value = {"result": "success", "stream_id": 99}
        client.get_messages_raw.return_value = {
            "result": "success",
            "messages": [{"id": 1}],
        }
        client.edit_message.return_value = {"result": "success"}

        result = await agents_channel_topic_ops("move", "src", "dest")
        assert result["status"] == "success"
        client.edit_message.assert_called_with(
            message_id=1, topic="dest", propagate_mode="change_all"
        )

    @pytest.mark.asyncio
    async def test_agents_channel_topic_ops_delete_unsafe(self, mock_deps):
        """Test delete requires unsafe mode."""
        client, mock_unsafe, _ = mock_deps
        client.get_stream_id.return_value = {"result": "success", "stream_id": 99}
        mock_unsafe.return_value = False

        result = await agents_channel_topic_ops("delete", "src")
        assert result["status"] == "error"
        assert "requires --unsafe mode" in result["error"]

    @pytest.mark.asyncio
    async def test_agents_channel_topic_ops_delete_success(self, mock_deps):
        """Test delete success."""
        client, mock_unsafe, _ = mock_deps
        client.get_stream_id.return_value = {"result": "success", "stream_id": 99}
        mock_unsafe.return_value = True
        client.delete_topic.return_value = {"result": "success"}

        result = await agents_channel_topic_ops("delete", "src")
        assert result["status"] == "success"
        client.delete_topic.assert_called_with(99, "src")

    @pytest.mark.asyncio
    async def test_agents_channel_topic_ops_mute(self, mock_deps):
        """Test mute topic."""
        client, _, _ = mock_deps
        client.get_stream_id.return_value = {"result": "success", "stream_id": 99}
        client.mute_topic.return_value = {"result": "success"}

        result = await agents_channel_topic_ops("mute", "src")
        assert result["status"] == "success"
        client.mute_topic.assert_called_with(99, "src")
