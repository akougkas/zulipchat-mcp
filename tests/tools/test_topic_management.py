"""Tests for tools/topic_management.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.topic_management import (
    get_stream_topics,
)


class TestTopicManagementTools:
    """Tests for topic management tools."""

    @pytest.fixture
    def mock_deps(self):
        with patch(
            "src.zulipchat_mcp.tools.topic_management.get_client"
        ) as mock_get_client:
            client = MagicMock()
            mock_get_client.return_value = client
            yield client, None, None

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
    async def test_get_stream_topics_by_name(self, mock_deps):
        client, _, _ = mock_deps
        client.get_stream_id.return_value = {"result": "success", "stream_id": 9}
        client.get_stream_topics.return_value = {"result": "success", "topics": []}

        result = await get_stream_topics(stream_name="Agent")

        assert result["stream_id"] == 9
        client.get_stream_topics.assert_called_once_with(9)
        assert (await get_stream_topics())["status"] == "error"
