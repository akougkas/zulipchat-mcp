"""Tests for tools/stream_management.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.stream_management import (
    get_stream_info,
    get_streams,
)


class TestGetStreams:
    """Tests for get_streams function."""

    @pytest.fixture
    def mock_deps(self):
        """Patch get_client to return mock client."""
        with patch(
            "src.zulipchat_mcp.tools.stream_management.get_client"
        ) as mock_get_client:
            client = MagicMock()
            mock_get_client.return_value = client
            yield client

    @pytest.mark.asyncio
    async def test_get_streams_success(self, mock_deps):
        """Test successful stream listing."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [
                {"name": "general", "stream_id": 1, "invite_only": False},
                {"name": "private", "stream_id": 2, "invite_only": True},
            ],
        }

        result = await get_streams()

        assert result["status"] == "success"
        assert result["count"] == 2
        assert len(result["streams"]) == 2
        mock_deps.get_streams.assert_called_once_with(
            include_subscribed=True, include_public=True
        )

    @pytest.mark.asyncio
    async def test_get_streams_compact_unless_verbose(self, mock_deps):
        """Default output drops Zulip permission/group fields."""
        raw = {
            "name": "general",
            "stream_id": 1,
            "description": "d",
            "invite_only": False,
            "can_administer_channel_group": {"direct_members": [7]},
            "stream_post_policy": 1,
        }
        mock_deps.get_streams.return_value = {"result": "success", "streams": [raw]}

        compact = await get_streams()
        verbose = await get_streams(verbose=True)

        assert compact["streams"] == [
            {
                "stream_id": 1,
                "name": "general",
                "description": "d",
                "invite_only": False,
            }
        ]
        assert verbose["streams"] == [raw]

    @pytest.mark.asyncio
    async def test_get_streams_filter_public(self, mock_deps):
        """Subscribed public streams remain when discovery of other public streams is off."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [
                {"name": "general", "stream_id": 1, "invite_only": False},
                {"name": "private", "stream_id": 2, "invite_only": True},
            ],
        }

        result = await get_streams(include_public=False)

        assert result["status"] == "success"
        assert result["count"] == 2
        mock_deps.get_streams.assert_called_once_with(
            include_subscribed=True, include_public=False
        )

    @pytest.mark.asyncio
    async def test_get_streams_not_subscribed(self, mock_deps):
        """Test with include_subscribed=False."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [{"name": "general", "stream_id": 1}],
        }

        result = await get_streams(include_subscribed=False)

        assert result["status"] == "success"
        mock_deps.get_streams.assert_called_once_with(
            include_subscribed=False, include_public=True
        )

    @pytest.mark.asyncio
    async def test_get_streams_api_error(self, mock_deps):
        """Test API error response."""
        mock_deps.get_streams.return_value = {
            "result": "error",
            "msg": "Permission denied",
        }

        result = await get_streams()

        assert result["status"] == "error"
        assert result["error"]["message"] == "Permission denied"

    @pytest.mark.asyncio
    async def test_get_streams_api_error_no_message(self, mock_deps):
        """Test API error without message."""
        mock_deps.get_streams.return_value = {"result": "error"}

        result = await get_streams()

        assert result["status"] == "error"
        assert result["error"]["message"] == "Failed to list streams"

    @pytest.mark.asyncio
    async def test_get_streams_exception(self, mock_deps):
        """Test exception handling."""
        mock_deps.get_streams.side_effect = Exception("Network error")

        result = await get_streams()

        assert result["status"] == "error"
        assert "Network error" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_streams_empty(self, mock_deps):
        """Test empty stream list."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [],
        }

        result = await get_streams()

        assert result["status"] == "success"
        assert result["count"] == 0
        assert result["streams"] == []


class TestGetStreamInfo:
    """Tests for get_stream_info function."""

    @pytest.fixture
    def mock_deps(self):
        """Patch get_client to return mock client."""
        with patch(
            "src.zulipchat_mcp.tools.stream_management.get_client"
        ) as mock_get_client:
            client = MagicMock()
            mock_get_client.return_value = client
            yield client

    @pytest.mark.asyncio
    async def test_get_stream_info_missing_params(self, mock_deps):
        """Test error when neither stream_name nor stream_id provided."""
        result = await get_stream_info()

        assert result["status"] == "error"
        assert (
            "Either stream_name or stream_id is required" in result["error"]["message"]
        )

    @pytest.mark.asyncio
    async def test_get_stream_info_by_id(self, mock_deps):
        """Test getting stream info by ID."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "General discussion",
                "invite_only": False,
                "is_web_public": True,
            },
        }

        result = await get_stream_info(stream_id=1)

        assert result["status"] == "success"
        assert result["stream_id"] == 1
        assert result["name"] == "general"
        assert result["description"] == "General discussion"
        assert result["invite_only"] is False
        assert result["is_web_public"] is True

    @pytest.mark.asyncio
    async def test_get_stream_info_by_name(self, mock_deps):
        """Test getting stream info by name."""
        mock_deps.get_stream_id.return_value = {
            "result": "success",
            "stream_id": 1,
        }
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "General discussion",
                "invite_only": False,
                "is_web_public": False,
            },
        }

        result = await get_stream_info(stream_name="general")

        assert result["status"] == "success"
        assert result["stream_id"] == 1
        assert result["name"] == "general"
        mock_deps.get_stream_id.assert_called_once_with("general")

    @pytest.mark.asyncio
    async def test_get_stream_info_name_not_found(self, mock_deps):
        """Test stream name not found."""
        mock_deps.get_stream_id.return_value = {
            "result": "error",
            "msg": "Invalid stream name",
        }

        result = await get_stream_info(stream_name="nonexistent")

        assert result["status"] == "error"
        assert result["error"]["message"] == "Invalid stream name"

    @pytest.mark.asyncio
    async def test_get_stream_info_fetches_one_channel_by_id(self, mock_deps):
        """An unknown ID surfaces the server error; no channel listing."""
        mock_deps.get_stream.return_value = {
            "result": "error",
            "code": "BAD_REQUEST",
            "msg": "Invalid channel ID",
        }

        result = await get_stream_info(stream_id=1)

        assert result["status"] == "error"
        assert result["error"]["message"] == "Invalid channel ID"
        mock_deps.get_stream.assert_called_once_with(1)
        mock_deps.get_streams.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_stream_info_get_streams_failed(self, mock_deps):
        """Test when get_streams API call fails."""
        mock_deps.get_stream.return_value = {
            "result": "error",
            "msg": "Permission denied",
        }

        result = await get_stream_info(stream_id=1)

        assert result["status"] == "error"
        assert result["error"]["message"] == "Permission denied"

    @pytest.mark.asyncio
    async def test_get_stream_info_with_subscribers(self, mock_deps):
        """Test including subscribers."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "",
                "invite_only": False,
                "is_web_public": False,
            },
        }
        mock_deps.get_subscribers.return_value = {
            "result": "success",
            "subscribers": [101, 102, 103],
        }

        result = await get_stream_info(stream_id=1, include_subscribers=True)

        assert result["status"] == "success"
        assert result["subscribers"] == [101, 102, 103]
        assert result["subscriber_count"] == 3
        mock_deps.get_subscribers.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_stream_info_subscribers_failed(self, mock_deps):
        """Test when get_subscribers fails - should still return basic info."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "",
                "invite_only": False,
                "is_web_public": False,
            },
        }
        mock_deps.get_subscribers.return_value = {
            "result": "error",
            "msg": "Not authorized",
        }

        result = await get_stream_info(stream_id=1, include_subscribers=True)

        assert result["status"] == "partial"
        assert result["stream_id"] == 1
        assert "subscribers" not in result
        assert result["errors"] == [
            {
                "component": "subscribers",
                "code": "ZULIP_ERROR",
                "message": "Not authorized",
                "retryable": False,
            }
        ]

    @pytest.mark.asyncio
    async def test_get_stream_info_with_topics(self, mock_deps):
        """Test including topics."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "",
                "invite_only": False,
                "is_web_public": False,
            },
        }
        mock_deps.get_stream_topics.return_value = {
            "result": "success",
            "topics": [
                {"name": "topic1", "max_id": 100},
                {"name": "topic2", "max_id": 200},
            ],
        }

        result = await get_stream_info(stream_id=1, include_topics=True)

        assert result["status"] == "success"
        assert len(result["topics"]) == 2
        assert result["topic_count"] == 2
        mock_deps.get_stream_topics.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_stream_info_topics_failed(self, mock_deps):
        """Test when get_stream_topics fails - should still return basic info."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "",
                "invite_only": False,
                "is_web_public": False,
            },
        }
        mock_deps.get_stream_topics.return_value = {
            "result": "error",
            "msg": "Not authorized",
        }

        result = await get_stream_info(stream_id=1, include_topics=True)

        assert result["status"] == "partial"
        assert result["stream_id"] == 1
        assert "topics" not in result
        assert result["errors"] == [
            {
                "component": "topics",
                "code": "ZULIP_ERROR",
                "message": "Not authorized",
                "retryable": False,
            }
        ]

    @pytest.mark.asyncio
    async def test_get_stream_info_with_both_subscribers_and_topics(self, mock_deps):
        """Test including both subscribers and topics."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "Test",
                "invite_only": True,
                "is_web_public": False,
            },
        }
        mock_deps.get_subscribers.return_value = {
            "result": "success",
            "subscribers": [101],
        }
        mock_deps.get_stream_topics.return_value = {
            "result": "success",
            "topics": [{"name": "topic1"}],
        }

        result = await get_stream_info(
            stream_id=1, include_subscribers=True, include_topics=True
        )

        assert result["status"] == "success"
        assert result["subscriber_count"] == 1
        assert result["topic_count"] == 1

    @pytest.mark.asyncio
    async def test_get_stream_info_exception(self, mock_deps):
        """Test exception handling."""
        mock_deps.get_stream.side_effect = Exception("Connection failed")

        result = await get_stream_info(stream_id=1)

        assert result["status"] == "error"
        assert "Connection failed" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_stream_info_by_name_with_id_provided(self, mock_deps):
        """Test when both name and id provided - should use id directly."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "general",
                "description": "",
                "invite_only": False,
                "is_web_public": False,
            },
        }

        result = await get_stream_info(stream_name="general", stream_id=1)

        assert result["status"] == "success"
        # Should NOT call get_stream_id when stream_id is provided
        mock_deps.get_stream_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_stream_info_missing_optional_fields(self, mock_deps):
        """Test stream with missing optional fields uses defaults."""
        mock_deps.get_stream.return_value = {
            "result": "success",
            "stream": {
                "stream_id": 1,
                "name": "minimal",
                # Missing description, invite_only, is_web_public
            },
        }

        result = await get_stream_info(stream_id=1)

        assert result["status"] == "success"
        assert result["description"] is None
        assert result["invite_only"] is False  # Default
        assert result["is_web_public"] is False  # Default
