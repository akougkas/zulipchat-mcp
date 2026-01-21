"""Comprehensive tests for tools/mark_messaging.py.

Covers all functions including edge cases, error handling, and the registration function.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP

from src.zulipchat_mcp.tools.mark_messaging import (
    _resolve_stream_name,
    mark_all_as_read,
    mark_messages_unread,
    mark_stream_as_read,
    mark_topic_as_read,
    register_mark_messaging_tools,
    star_messages,
    unstar_messages,
    update_message_flags_for_narrow,
)


class TestResolveStreamName:
    """Tests for the _resolve_stream_name helper function."""

    @pytest.fixture
    def mock_deps(self):
        """Patch dependencies for stream resolution."""
        mock_client = MagicMock()
        with (
            patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    def test_resolve_stream_name_success(self, mock_deps):
        """Test successful stream name resolution."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [
                {"stream_id": 123, "name": "General"},
                {"stream_id": 456, "name": "Engineering"},
            ],
        }

        result = _resolve_stream_name(123)
        assert result == "General"

    def test_resolve_stream_name_not_found(self, mock_deps):
        """Test stream ID not found raises ValueError."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [{"stream_id": 123, "name": "General"}],
        }

        with pytest.raises(ValueError, match="Unknown stream ID: 999"):
            _resolve_stream_name(999)

    def test_resolve_stream_name_api_failure(self, mock_deps):
        """Test API failure raises ValueError."""
        mock_deps.get_streams.return_value = {
            "result": "error",
            "msg": "Not authorized",
        }

        with pytest.raises(ValueError, match="Unknown stream ID"):
            _resolve_stream_name(123)

    def test_resolve_stream_name_empty_streams(self, mock_deps):
        """Test empty streams list raises ValueError."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [],
        }

        with pytest.raises(ValueError, match="Unknown stream ID"):
            _resolve_stream_name(123)


class TestUpdateMessageFlagsForNarrow:
    """Tests for update_message_flags_for_narrow function."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {
            "result": "success",
            "processed_count": 10,
            "updated_count": 5,
            "first_processed_id": 100,
            "last_processed_id": 109,
            "found_oldest": True,
            "found_newest": True,
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_update_flags_success_full_response(self, mock_deps):
        """Test successful flag update with all response fields."""
        narrow = [{"operator": "stream", "operand": "general"}]
        result = await update_message_flags_for_narrow(
            narrow=narrow, op="add", flag="read"
        )

        assert result["status"] == "success"
        assert result["operation"] == "add_read"
        assert result["processed_count"] == 10
        assert result["updated_count"] == 5
        assert result["first_processed_id"] == 100
        assert result["last_processed_id"] == 109
        assert result["found_oldest"] is True
        assert result["found_newest"] is True

    @pytest.mark.asyncio
    async def test_update_flags_with_custom_params(self, mock_deps):
        """Test flag update with custom anchor and range parameters."""
        narrow = [{"operator": "is", "operand": "starred"}]
        await update_message_flags_for_narrow(
            narrow=narrow,
            op="remove",
            flag="starred",
            anchor="oldest",
            include_anchor=False,
            num_before=25,
            num_after=75,
        )

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["anchor"] == "oldest"
        assert request["include_anchor"] is False
        assert request["num_before"] == 25
        assert request["num_after"] == 75

    @pytest.mark.asyncio
    async def test_update_flags_with_integer_anchor(self, mock_deps):
        """Test flag update with integer anchor (message ID)."""
        await update_message_flags_for_narrow(
            narrow=[], op="add", flag="read", anchor=12345
        )

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["anchor"] == 12345

    @pytest.mark.asyncio
    async def test_update_flags_api_error(self, mock_deps):
        """Test handling of API error response."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Invalid narrow operator",
        }

        result = await update_message_flags_for_narrow(
            narrow=[{"operator": "invalid", "operand": "value"}],
            op="add",
            flag="read",
        )

        assert result["status"] == "error"
        assert "Invalid narrow operator" in result["error"]

    @pytest.mark.asyncio
    async def test_update_flags_exception_handling(self, mock_deps):
        """Test exception handling in update_message_flags_for_narrow."""
        mock_deps.client.call_endpoint.side_effect = Exception("Network error")

        result = await update_message_flags_for_narrow(
            narrow=[], op="add", flag="read"
        )

        assert result["status"] == "error"
        assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_update_flags_minimal_response(self, mock_deps):
        """Test handling of minimal API response (missing optional fields)."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
        }

        result = await update_message_flags_for_narrow(
            narrow=[], op="add", flag="read"
        )

        assert result["status"] == "success"
        assert result["processed_count"] == 0
        assert result["updated_count"] == 0
        assert result["first_processed_id"] is None
        assert result["last_processed_id"] is None
        assert result["found_oldest"] is False
        assert result["found_newest"] is False


class TestMarkAllAsRead:
    """Tests for mark_all_as_read function."""

    @pytest.fixture
    def mock_deps(self):
        """Patch dependencies."""
        mock_client = MagicMock()
        mock_client.client.call_endpoint.return_value = {
            "result": "success",
            "processed_count": 100,
            "updated_count": 50,
        }
        with (
            patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_mark_all_as_read_success(self, mock_deps):
        """Test marking all messages as read."""
        result = await mark_all_as_read()

        assert result["status"] == "success"
        assert result["operation"] == "add_read"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == []
        assert request["anchor"] == "first_unread"
        assert request["num_before"] == 0
        assert request["num_after"] == 1000

    @pytest.mark.asyncio
    async def test_mark_all_as_read_exception(self, mock_deps):
        """Test exception handling in mark_all_as_read."""
        mock_deps.client.call_endpoint.side_effect = Exception("Connection failed")

        result = await mark_all_as_read()

        assert result["status"] == "error"
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_mark_all_as_read_outer_exception(self):
        """Test outer exception handler in mark_all_as_read."""
        # Patch the inner function to raise an exception
        with patch(
            "src.zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow"
        ) as mock_inner:
            mock_inner.side_effect = Exception("Unexpected outer error")
            result = await mark_all_as_read()

        assert result["status"] == "error"
        assert "Unexpected outer error" in result["error"]


class TestMarkTopicAsRead:
    """Tests for mark_topic_as_read function."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {
            "result": "success",
            "processed_count": 20,
            "updated_count": 15,
        }
        client.get_streams.return_value = {
            "result": "success",
            "streams": [
                {"stream_id": 123, "name": "Engineering"},
                {"stream_id": 456, "name": "General"},
            ],
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_mark_topic_as_read_success(self, mock_deps):
        """Test marking a topic as read."""
        result = await mark_topic_as_read(123, "bug-fixes")

        assert result["status"] == "success"
        assert result["operation"] == "add_read"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [
            {"operator": "stream", "operand": "Engineering"},
            {"operator": "topic", "operand": "bug-fixes"},
        ]

    @pytest.mark.asyncio
    async def test_mark_topic_as_read_invalid_stream(self, mock_deps):
        """Test marking topic with invalid stream ID."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [{"stream_id": 123, "name": "Engineering"}],
        }

        result = await mark_topic_as_read(999, "some-topic")

        assert result["status"] == "error"
        assert "Unknown stream ID: 999" in result["error"]

    @pytest.mark.asyncio
    async def test_mark_topic_as_read_exception(self, mock_deps):
        """Test exception handling in mark_topic_as_read."""
        mock_deps.get_streams.side_effect = Exception("API timeout")

        result = await mark_topic_as_read(123, "topic")

        assert result["status"] == "error"
        assert "API timeout" in result["error"]


class TestMarkMessagesUnread:
    """Tests for mark_messages_unread function."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {
            "result": "success",
            "processed_count": 10,
            "updated_count": 10,
        }
        client.get_streams.return_value = {
            "result": "success",
            "streams": [
                {"stream_id": 123, "name": "Engineering"},
            ],
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_mark_messages_unread_with_narrow(self, mock_deps):
        """Test marking messages unread with explicit narrow."""
        narrow = [{"operator": "sender", "operand": "user@example.com"}]
        result = await mark_messages_unread(narrow=narrow)

        assert result["status"] == "success"
        assert result["operation"] == "remove_read"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == narrow
        assert request["op"] == "remove"
        assert request["flag"] == "read"

    @pytest.mark.asyncio
    async def test_mark_messages_unread_by_stream_id(self, mock_deps):
        """Test marking messages unread by stream ID."""
        result = await mark_messages_unread(stream_id=123)

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [{"operator": "stream", "operand": "Engineering"}]

    @pytest.mark.asyncio
    async def test_mark_messages_unread_by_topic(self, mock_deps):
        """Test marking messages unread by topic (without stream)."""
        result = await mark_messages_unread(topic_name="announcements")

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [{"operator": "topic", "operand": "announcements"}]

    @pytest.mark.asyncio
    async def test_mark_messages_unread_by_sender(self, mock_deps):
        """Test marking messages unread by sender email."""
        result = await mark_messages_unread(sender_email="alice@example.com")

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [
            {"operator": "sender", "operand": "alice@example.com"}
        ]

    @pytest.mark.asyncio
    async def test_mark_messages_unread_combined_filters(self, mock_deps):
        """Test marking messages unread with multiple filters."""
        result = await mark_messages_unread(
            stream_id=123,
            topic_name="releases",
            sender_email="bob@example.com",
        )

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert {"operator": "stream", "operand": "Engineering"} in request["narrow"]
        assert {"operator": "topic", "operand": "releases"} in request["narrow"]
        assert {"operator": "sender", "operand": "bob@example.com"} in request["narrow"]

    @pytest.mark.asyncio
    async def test_mark_messages_unread_empty_criteria(self, mock_deps):
        """Test marking messages unread with no criteria returns error."""
        result = await mark_messages_unread()

        assert result["status"] == "error"
        assert "Must provide narrow" in result["error"]

    @pytest.mark.asyncio
    async def test_mark_messages_unread_invalid_stream(self, mock_deps):
        """Test marking messages unread with invalid stream ID."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [],
        }

        result = await mark_messages_unread(stream_id=999)

        assert result["status"] == "error"
        assert "Unknown stream ID: 999" in result["error"]

    @pytest.mark.asyncio
    async def test_mark_messages_unread_exception(self, mock_deps):
        """Test exception handling in mark_messages_unread."""
        mock_deps.client.call_endpoint.side_effect = Exception("Server error")

        result = await mark_messages_unread(
            narrow=[{"operator": "is", "operand": "private"}]
        )

        assert result["status"] == "error"
        assert "Server error" in result["error"]

    @pytest.mark.asyncio
    async def test_mark_messages_unread_outer_exception(self):
        """Test outer exception handler in mark_messages_unread."""
        with patch(
            "src.zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow"
        ) as mock_inner:
            mock_inner.side_effect = Exception("Unexpected outer error")
            result = await mark_messages_unread(
                narrow=[{"operator": "is", "operand": "private"}]
            )

        assert result["status"] == "error"
        assert "Unexpected outer error" in result["error"]


class TestStarMessages:
    """Tests for star_messages function."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {
            "result": "success",
            "processed_count": 5,
            "updated_count": 5,
        }
        client.get_streams.return_value = {
            "result": "success",
            "streams": [{"stream_id": 123, "name": "Important"}],
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_star_messages_with_narrow(self, mock_deps):
        """Test starring messages with explicit narrow."""
        narrow = [{"operator": "is", "operand": "mentioned"}]
        result = await star_messages(narrow=narrow)

        assert result["status"] == "success"
        assert result["operation"] == "add_starred"

    @pytest.mark.asyncio
    async def test_star_messages_by_stream_id(self, mock_deps):
        """Test starring messages by stream ID."""
        result = await star_messages(stream_id=123)

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [{"operator": "stream", "operand": "Important"}]
        assert request["flag"] == "starred"
        assert request["op"] == "add"

    @pytest.mark.asyncio
    async def test_star_messages_by_topic(self, mock_deps):
        """Test starring messages by topic."""
        result = await star_messages(topic_name="urgent")

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [{"operator": "topic", "operand": "urgent"}]

    @pytest.mark.asyncio
    async def test_star_messages_by_sender(self, mock_deps):
        """Test starring messages by sender."""
        result = await star_messages(sender_email="vip@example.com")

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [
            {"operator": "sender", "operand": "vip@example.com"}
        ]

    @pytest.mark.asyncio
    async def test_star_messages_empty_criteria(self, mock_deps):
        """Test starring with no criteria returns error."""
        result = await star_messages()

        assert result["status"] == "error"
        assert "Must provide narrow" in result["error"]

    @pytest.mark.asyncio
    async def test_star_messages_invalid_stream(self, mock_deps):
        """Test starring with invalid stream ID."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [],
        }

        result = await star_messages(stream_id=999)

        assert result["status"] == "error"
        assert "Unknown stream ID: 999" in result["error"]

    @pytest.mark.asyncio
    async def test_star_messages_exception(self, mock_deps):
        """Test exception handling in star_messages."""
        mock_deps.client.call_endpoint.side_effect = Exception("Rate limited")

        result = await star_messages(narrow=[{"operator": "is", "operand": "private"}])

        assert result["status"] == "error"
        assert "Rate limited" in result["error"]

    @pytest.mark.asyncio
    async def test_star_messages_outer_exception(self):
        """Test outer exception handler in star_messages."""
        with patch(
            "src.zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow"
        ) as mock_inner:
            mock_inner.side_effect = Exception("Unexpected outer error")
            result = await star_messages(
                narrow=[{"operator": "is", "operand": "private"}]
            )

        assert result["status"] == "error"
        assert "Unexpected outer error" in result["error"]


class TestUnstarMessages:
    """Tests for unstar_messages function."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {
            "result": "success",
            "processed_count": 3,
            "updated_count": 3,
        }
        client.get_streams.return_value = {
            "result": "success",
            "streams": [{"stream_id": 123, "name": "Archive"}],
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_unstar_messages_with_narrow(self, mock_deps):
        """Test unstarring messages with explicit narrow."""
        narrow = [{"operator": "is", "operand": "starred"}]
        result = await unstar_messages(narrow=narrow)

        assert result["status"] == "success"
        assert result["operation"] == "remove_starred"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["op"] == "remove"
        assert request["flag"] == "starred"

    @pytest.mark.asyncio
    async def test_unstar_messages_by_stream_id(self, mock_deps):
        """Test unstarring messages by stream ID."""
        result = await unstar_messages(stream_id=123)

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [{"operator": "stream", "operand": "Archive"}]

    @pytest.mark.asyncio
    async def test_unstar_messages_by_topic(self, mock_deps):
        """Test unstarring messages by topic."""
        result = await unstar_messages(topic_name="old-stuff")

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [{"operator": "topic", "operand": "old-stuff"}]

    @pytest.mark.asyncio
    async def test_unstar_messages_by_sender(self, mock_deps):
        """Test unstarring messages by sender."""
        result = await unstar_messages(sender_email="old-colleague@example.com")

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == [
            {"operator": "sender", "operand": "old-colleague@example.com"}
        ]

    @pytest.mark.asyncio
    async def test_unstar_messages_combined_filters(self, mock_deps):
        """Test unstarring messages with multiple filters."""
        result = await unstar_messages(
            stream_id=123,
            topic_name="cleanup",
            sender_email="cleanup-bot@example.com",
        )

        assert result["status"] == "success"

        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert len(request["narrow"]) == 3

    @pytest.mark.asyncio
    async def test_unstar_messages_empty_criteria(self, mock_deps):
        """Test unstarring with no criteria returns error."""
        result = await unstar_messages()

        assert result["status"] == "error"
        assert "Must provide narrow" in result["error"]

    @pytest.mark.asyncio
    async def test_unstar_messages_invalid_stream(self, mock_deps):
        """Test unstarring with invalid stream ID."""
        mock_deps.get_streams.return_value = {
            "result": "success",
            "streams": [],
        }

        result = await unstar_messages(stream_id=999)

        assert result["status"] == "error"
        assert "Unknown stream ID: 999" in result["error"]

    @pytest.mark.asyncio
    async def test_unstar_messages_exception(self, mock_deps):
        """Test exception handling in unstar_messages."""
        mock_deps.client.call_endpoint.side_effect = Exception("Connection reset")

        result = await unstar_messages(
            narrow=[{"operator": "is", "operand": "starred"}]
        )

        assert result["status"] == "error"
        assert "Connection reset" in result["error"]

    @pytest.mark.asyncio
    async def test_unstar_messages_outer_exception(self):
        """Test outer exception handler in unstar_messages."""
        with patch(
            "src.zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow"
        ) as mock_inner:
            mock_inner.side_effect = Exception("Unexpected outer error")
            result = await unstar_messages(
                narrow=[{"operator": "is", "operand": "starred"}]
            )

        assert result["status"] == "error"
        assert "Unexpected outer error" in result["error"]


class TestRegisterMarkMessagingTools:
    """Tests for register_mark_messaging_tools function."""

    def test_register_tools(self):
        """Test that all mark messaging tools are registered."""
        mcp = MagicMock(spec=FastMCP)
        mock_tool_decorator = MagicMock(return_value=lambda x: x)
        mcp.tool.return_value = mock_tool_decorator

        register_mark_messaging_tools(mcp)

        # Verify all 7 tools are registered
        assert mcp.tool.call_count == 7

        # Extract all tool names from the calls
        tool_names = [call.kwargs.get("name") for call in mcp.tool.call_args_list]

        expected_tools = [
            "update_message_flags_for_narrow",
            "mark_all_as_read",
            "mark_stream_as_read",
            "mark_topic_as_read",
            "mark_messages_unread",
            "star_messages",
            "unstar_messages",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Missing tool: {expected_tool}"

    def test_register_tools_descriptions(self):
        """Test that registered tools have descriptions."""
        mcp = MagicMock(spec=FastMCP)
        mock_tool_decorator = MagicMock(return_value=lambda x: x)
        mcp.tool.return_value = mock_tool_decorator

        register_mark_messaging_tools(mcp)

        # All calls should have descriptions
        for call in mcp.tool.call_args_list:
            assert "description" in call.kwargs
            assert len(call.kwargs["description"]) > 0
