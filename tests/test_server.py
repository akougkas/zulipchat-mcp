"""Comprehensive tests for all MCP server tools to achieve 95% coverage.

Tests all 8 MCP tools + 3 resources + 3 prompts with edge cases, error scenarios,
and validation logic as specified in the requirements document.
"""

from unittest.mock import Mock, patch

import pytest

from zulipchat_mcp.client import ZulipMessage, ZulipStream, ZulipUser
from zulipchat_mcp.exceptions import ConnectionError, ValidationError


class TestSendMessageTool:
    """Comprehensive tests for send_message MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_send_message_stream_success(self, mock_get_client):
        """Test successful stream message sending."""
        from zulipchat_mcp.server import send_message

        mock_client = Mock()
        mock_client.send_message.return_value = {"result": "success", "id": 123}
        mock_get_client.return_value = mock_client

        result = send_message("stream", "general", "Hello world!", "test-topic")

        assert result["status"] == "success"
        assert result["message_id"] == 123
        assert "timestamp" in result
        mock_client.send_message.assert_called_once_with(
            "stream", "general", "Hello world!", "test-topic"
        )

    @patch("zulipchat_mcp.server.get_client")
    def test_send_message_private_success(self, mock_get_client):
        """Test successful private message sending."""
        from zulipchat_mcp.server import send_message

        mock_client = Mock()
        mock_client.send_message.return_value = {"result": "success", "id": 456}
        mock_get_client.return_value = mock_client

        result = send_message("private", "user@example.com", "Hello!")

        assert result["status"] == "success"
        assert result["message_id"] == 456
        mock_client.send_message.assert_called_once_with(
            "private", ["user@example.com"], "Hello!", None
        )

    def test_send_message_invalid_type(self):
        """Test send_message with invalid message type."""
        from zulipchat_mcp.server import send_message

        result = send_message("invalid", "general", "Hello!", "topic")

        assert result["status"] == "error"
        assert "Invalid message_type" in result["error"]

    def test_send_message_stream_missing_topic(self):
        """Test stream message without required topic."""
        from zulipchat_mcp.server import send_message

        result = send_message("stream", "general", "Hello!")

        assert result["status"] == "error"
        assert "Topic required for stream messages" in result["error"]

    def test_send_message_invalid_stream_name(self):
        """Test send_message with invalid stream name."""
        from zulipchat_mcp.server import send_message

        result = send_message("stream", "invalid<script>", "Hello!", "topic")

        assert result["status"] == "error"
        assert "Invalid stream name" in result["error"]

    def test_send_message_invalid_topic(self):
        """Test send_message with invalid topic."""
        from zulipchat_mcp.server import send_message

        result = send_message("stream", "general", "Hello!", "invalid<script>topic")

        assert result["status"] == "error"
        assert "Invalid topic" in result["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_send_message_api_failure(self, mock_get_client):
        """Test send_message when API returns failure."""
        from zulipchat_mcp.server import send_message

        mock_client = Mock()
        mock_client.send_message.return_value = {
            "result": "error",
            "msg": "Stream does not exist",
        }
        mock_get_client.return_value = mock_client

        result = send_message("stream", "nonexistent", "Hello!", "topic")

        assert result["status"] == "error"
        assert "Stream does not exist" in result["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_send_message_sanitizes_content(self, mock_get_client):
        """Test that message content gets sanitized."""
        from zulipchat_mcp.server import send_message

        mock_client = Mock()
        mock_client.send_message.return_value = {"result": "success", "id": 123}
        mock_get_client.return_value = mock_client

        send_message("stream", "general", "<script>alert('xss')</script>", "topic")

        # Should sanitize the content before sending
        called_args = mock_client.send_message.call_args[0]
        assert "&lt;script&gt;" in called_args[2]  # Content should be HTML escaped

    @patch("zulipchat_mcp.server.get_client")
    def test_send_message_exception_handling(self, mock_get_client):
        """Test exception handling in send_message."""
        from zulipchat_mcp.server import send_message

        mock_client = Mock()
        mock_client.send_message.side_effect = ValueError("Invalid input")
        mock_get_client.return_value = mock_client

        result = send_message("stream", "general", "Hello!", "topic")

        assert result["status"] == "error"
        assert "error" in result


class TestGetMessagesTool:
    """Comprehensive tests for get_messages MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_get_messages_from_stream(self, mock_get_client):
        """Test getting messages from a specific stream."""
        from zulipchat_mcp.server import get_messages

        mock_message = ZulipMessage(
            id=1,
            sender_full_name="John",
            sender_email="john@test.com",
            timestamp=123456,
            content="Hello!",
            type="stream",
            stream_name="general",
            subject="topic1",
        )

        mock_client = Mock()
        mock_client.get_messages_from_stream.return_value = [mock_message]
        mock_get_client.return_value = mock_client

        result = get_messages("general", "topic1", 24, 50)

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["sender"] == "John"
        assert result[0]["stream"] == "general"
        assert result[0]["topic"] == "topic1"

    @patch("zulipchat_mcp.server.get_client")
    def test_get_messages_all_streams(self, mock_get_client):
        """Test getting messages from all streams."""
        from zulipchat_mcp.server import get_messages

        mock_message = ZulipMessage(
            id=2,
            sender_full_name="Alice",
            sender_email="alice@test.com",
            timestamp=123457,
            content="Hi there!",
            type="stream",
        )

        mock_client = Mock()
        mock_client.get_messages.return_value = [mock_message]
        mock_get_client.return_value = mock_client

        result = get_messages(limit=25)

        assert len(result) == 1
        assert result[0]["id"] == 2
        mock_client.get_messages.assert_called_once_with(num_before=25)

    def test_get_messages_invalid_stream_name(self):
        """Test get_messages with invalid stream name."""
        from zulipchat_mcp.server import get_messages

        result = get_messages("invalid<script>stream")

        assert len(result) == 1
        assert "error" in result[0]
        assert "Invalid stream name" in result[0]["error"]

    def test_get_messages_invalid_topic(self):
        """Test get_messages with invalid topic."""
        from zulipchat_mcp.server import get_messages

        result = get_messages("general", "invalid<script>topic")

        assert len(result) == 1
        assert "error" in result[0]
        assert "Invalid topic" in result[0]["error"]

    def test_get_messages_invalid_hours_back(self):
        """Test get_messages with invalid hours_back."""
        from zulipchat_mcp.server import get_messages

        result = get_messages("general", hours_back=200)  # Max is 168

        assert len(result) == 1
        assert "error" in result[0]
        assert "hours_back must be between 1 and 168" in result[0]["error"]

    def test_get_messages_invalid_limit(self):
        """Test get_messages with invalid limit."""
        from zulipchat_mcp.server import get_messages

        result = get_messages("general", limit=150)  # Max is 100

        assert len(result) == 1
        assert "error" in result[0]
        assert "limit must be between 1 and 100" in result[0]["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_get_messages_connection_error(self, mock_get_client):
        """Test get_messages with connection error."""
        from zulipchat_mcp.server import get_messages

        mock_client = Mock()
        mock_client.get_messages_from_stream.side_effect = ConnectionError(
            "Connection failed"
        )
        mock_get_client.return_value = mock_client

        result = get_messages("general")

        assert len(result) == 1
        assert "error" in result[0]
        assert "Failed to retrieve messages" in result[0]["error"]


class TestSearchMessagesTool:
    """Comprehensive tests for search_messages MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_search_messages_success(self, mock_get_client):
        """Test successful message search."""
        from zulipchat_mcp.server import search_messages

        mock_message = ZulipMessage(
            id=1,
            sender_full_name="John",
            sender_email="john@test.com",
            timestamp=123456,
            content="deployment error",
            type="stream",
            stream_name="general",
            subject="issues",
        )

        mock_client = Mock()
        mock_client.search_messages.return_value = [mock_message]
        mock_get_client.return_value = mock_client

        result = search_messages("deployment", 50)

        assert len(result) == 1
        assert result[0]["content"] == "deployment error"
        mock_client.search_messages.assert_called_once_with(
            "deployment", num_results=50
        )

    def test_search_messages_empty_query(self):
        """Test search with empty query."""
        from zulipchat_mcp.server import search_messages

        result = search_messages("", 50)

        assert len(result) == 1
        assert "error" in result[0]
        assert "Query cannot be empty" in result[0]["error"]

    def test_search_messages_invalid_limit(self):
        """Test search with invalid limit."""
        from zulipchat_mcp.server import search_messages

        result = search_messages("test", 150)  # Max is 100

        assert len(result) == 1
        assert "error" in result[0]
        assert "limit must be between 1 and 100" in result[0]["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_search_messages_sanitizes_query(self, mock_get_client):
        """Test that search query gets sanitized."""
        from zulipchat_mcp.server import search_messages

        mock_client = Mock()
        mock_client.search_messages.return_value = []
        mock_get_client.return_value = mock_client

        search_messages("<script>alert('xss')</script>", 20)

        called_args = mock_client.search_messages.call_args[0]
        assert "&lt;script&gt;" in called_args[0]  # Query should be sanitized


class TestStreamsTool:
    """Comprehensive tests for get_streams MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_get_streams_success(self, mock_get_client):
        """Test successful streams retrieval."""
        from zulipchat_mcp.server import get_streams

        mock_stream = ZulipStream(
            stream_id=1,
            name="general",
            description="General discussion",
            is_private=False,
        )

        mock_client = Mock()
        mock_client.get_streams.return_value = [mock_stream]
        mock_get_client.return_value = mock_client

        result = get_streams()

        assert len(result) == 1
        assert result[0]["name"] == "general"
        assert result[0]["is_private"] is False

    @patch("zulipchat_mcp.server.get_client")
    def test_get_streams_connection_error(self, mock_get_client):
        """Test get_streams with connection error."""
        from zulipchat_mcp.server import get_streams

        mock_client = Mock()
        mock_client.get_streams.side_effect = ConnectionError("API unavailable")
        mock_get_client.return_value = mock_client

        result = get_streams()

        assert len(result) == 1
        assert "error" in result[0]
        assert "Failed to retrieve streams" in result[0]["error"]


class TestUsersTool:
    """Comprehensive tests for get_users MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_get_users_success(self, mock_get_client):
        """Test successful users retrieval."""
        from zulipchat_mcp.server import get_users

        mock_user = ZulipUser(
            user_id=1,
            full_name="John Doe",
            email="john@test.com",
            is_active=True,
            is_bot=False,
        )

        mock_client = Mock()
        mock_client.get_users.return_value = [mock_user]
        mock_get_client.return_value = mock_client

        result = get_users()

        assert len(result) == 1
        assert result[0]["full_name"] == "John Doe"
        assert result[0]["is_bot"] is False

    @patch("zulipchat_mcp.server.get_client")
    def test_get_users_error_handling(self, mock_get_client):
        """Test get_users error handling."""
        from zulipchat_mcp.server import get_users

        mock_client = Mock()
        mock_client.get_users.side_effect = Exception("Unexpected error")
        mock_get_client.return_value = mock_client

        result = get_users()

        assert len(result) == 1
        assert "error" in result[0]
        assert "An unexpected error occurred" in result[0]["error"]


class TestAddReactionTool:
    """Comprehensive tests for add_reaction MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_add_reaction_success(self, mock_get_client):
        """Test successful reaction addition."""
        from zulipchat_mcp.server import add_reaction

        mock_client = Mock()
        mock_client.add_reaction.return_value = {"result": "success"}
        mock_get_client.return_value = mock_client

        result = add_reaction(123, "thumbs_up")

        assert result["status"] == "success"
        assert result["message"] == "Reaction added"
        mock_client.add_reaction.assert_called_once_with(123, "thumbs_up")

    def test_add_reaction_invalid_message_id(self):
        """Test add_reaction with invalid message ID."""
        from zulipchat_mcp.server import add_reaction

        result = add_reaction(-1, "thumbs_up")

        assert result["status"] == "error"
        assert "Invalid message ID" in result["error"]

    def test_add_reaction_invalid_emoji(self):
        """Test add_reaction with invalid emoji name."""
        from zulipchat_mcp.server import add_reaction

        result = add_reaction(123, "invalid<script>emoji")

        assert result["status"] == "error"
        assert "Invalid emoji name" in result["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_add_reaction_api_failure(self, mock_get_client):
        """Test add_reaction when API fails."""
        from zulipchat_mcp.server import add_reaction

        mock_client = Mock()
        mock_client.add_reaction.return_value = {
            "result": "error",
            "msg": "Message not found",
        }
        mock_get_client.return_value = mock_client

        result = add_reaction(999, "thumbs_up")

        assert result["status"] == "error"
        assert "Message not found" in result["error"]


class TestEditMessageTool:
    """Comprehensive tests for edit_message MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_edit_message_content_success(self, mock_get_client):
        """Test successful message content editing."""
        from zulipchat_mcp.server import edit_message

        mock_client = Mock()
        mock_client.edit_message.return_value = {"result": "success"}
        mock_get_client.return_value = mock_client

        result = edit_message(123, content="Updated content")

        assert result["status"] == "success"
        assert result["message"] == "Message edited"
        mock_client.edit_message.assert_called_once_with(123, "Updated content", None)

    @patch("zulipchat_mcp.server.get_client")
    def test_edit_message_topic_success(self, mock_get_client):
        """Test successful message topic editing."""
        from zulipchat_mcp.server import edit_message

        mock_client = Mock()
        mock_client.edit_message.return_value = {"result": "success"}
        mock_get_client.return_value = mock_client

        result = edit_message(123, topic="New topic")

        assert result["status"] == "success"
        mock_client.edit_message.assert_called_once_with(123, None, "New topic")

    def test_edit_message_invalid_message_id(self):
        """Test edit_message with invalid message ID."""
        from zulipchat_mcp.server import edit_message

        result = edit_message(0, content="New content")

        assert result["status"] == "error"
        assert "Invalid message ID" in result["error"]

    def test_edit_message_invalid_topic(self):
        """Test edit_message with invalid topic."""
        from zulipchat_mcp.server import edit_message

        result = edit_message(123, topic="invalid<script>topic")

        assert result["status"] == "error"
        assert "Invalid topic" in result["error"]

    def test_edit_message_no_changes(self):
        """Test edit_message without content or topic."""
        from zulipchat_mcp.server import edit_message

        result = edit_message(123)

        assert result["status"] == "error"
        assert "Must provide content or topic to edit" in result["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_edit_message_sanitizes_content(self, mock_get_client):
        """Test that edited content gets sanitized."""
        from zulipchat_mcp.server import edit_message

        mock_client = Mock()
        mock_client.edit_message.return_value = {"result": "success"}
        mock_get_client.return_value = mock_client

        edit_message(123, content="<script>alert('xss')</script>")

        called_args = mock_client.edit_message.call_args[0]
        assert "&lt;script&gt;" in called_args[1]  # Content should be sanitized


class TestGetDailySummaryTool:
    """Comprehensive tests for get_daily_summary MCP tool."""

    @patch("zulipchat_mcp.server.get_client")
    def test_get_daily_summary_success(self, mock_get_client):
        """Test successful daily summary generation."""
        from zulipchat_mcp.server import get_daily_summary

        mock_summary = {
            "total_messages": 10,
            "streams": {
                "general": {"message_count": 5, "topics": {"topic1": 3, "topic2": 2}}
            },
            "top_senders": {"Alice": 4, "Bob": 3},
        }

        mock_client = Mock()
        mock_client.get_daily_summary.return_value = mock_summary
        mock_get_client.return_value = mock_client

        result = get_daily_summary(["general"], 24)

        assert result["status"] == "success"
        assert result["data"]["total_messages"] == 10
        mock_client.get_daily_summary.assert_called_once_with(["general"], 24)

    def test_get_daily_summary_invalid_stream(self):
        """Test daily summary with invalid stream name."""
        from zulipchat_mcp.server import get_daily_summary

        result = get_daily_summary(["invalid<script>stream"], 24)

        assert result["status"] == "error"
        assert "Invalid stream name" in result["error"]

    def test_get_daily_summary_invalid_hours_back(self):
        """Test daily summary with invalid hours_back."""
        from zulipchat_mcp.server import get_daily_summary

        result = get_daily_summary(["general"], 200)  # Max is 168

        assert result["status"] == "error"
        assert "hours_back must be between 1 and 168" in result["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_get_daily_summary_multiple_streams(self, mock_get_client):
        """Test daily summary with multiple streams."""
        from zulipchat_mcp.server import get_daily_summary

        mock_summary = {
            "total_messages": 25,
            "streams": {
                "general": {"message_count": 15, "topics": {"topic1": 10, "topic2": 5}},
                "development": {
                    "message_count": 10,
                    "topics": {"bugs": 6, "features": 4},
                },
            },
        }

        mock_client = Mock()
        mock_client.get_daily_summary.return_value = mock_summary
        mock_get_client.return_value = mock_client

        result = get_daily_summary(["general", "development"], 48)

        assert result["status"] == "success"
        assert result["data"]["total_messages"] == 25
        assert len(result["data"]["streams"]) == 2


class TestMCPResources:
    """Tests for MCP resources (stream messages, streams list, users list)."""

    @patch("zulipchat_mcp.server.get_client")
    def test_get_stream_messages_resource(self, mock_get_client):
        """Test stream messages resource."""
        from zulipchat_mcp.server import get_stream_messages

        mock_message = ZulipMessage(
            id=1,
            sender_full_name="John",
            sender_email="john@test.com",
            timestamp=1640995200,
            content="Hello!",
            type="stream",
            stream_name="general",
            subject="topic1",
        )

        mock_client = Mock()
        mock_client.get_messages_from_stream.return_value = [mock_message]
        mock_get_client.return_value = mock_client

        result = get_stream_messages("general")

        assert len(result) == 1
        assert "Messages from #general" in result[0].text
        assert "John" in result[0].text
        assert "Hello!" in result[0].text

    def test_get_stream_messages_invalid_stream(self):
        """Test stream messages resource with invalid stream."""
        from zulipchat_mcp.server import get_stream_messages

        result = get_stream_messages("invalid<script>stream")

        assert len(result) == 1
        assert "Invalid stream name" in result[0].text

    @patch("zulipchat_mcp.server.get_client")
    def test_list_streams_resource(self, mock_get_client):
        """Test streams list resource."""
        from zulipchat_mcp.server import list_streams

        mock_stream = ZulipStream(
            stream_id=1,
            name="general",
            description="General discussion",
            is_private=False,
        )

        mock_client = Mock()
        mock_client.get_streams.return_value = [mock_stream]
        mock_get_client.return_value = mock_client

        result = list_streams()

        assert len(result) == 1
        assert "Available Zulip Streams" in result[0].text
        assert "general" in result[0].text
        assert "📢 Public" in result[0].text

    @patch("zulipchat_mcp.server.get_client")
    def test_list_users_resource(self, mock_get_client):
        """Test users list resource."""
        from zulipchat_mcp.server import list_users

        active_user = ZulipUser(
            user_id=1,
            full_name="John Doe",
            email="john@test.com",
            is_active=True,
            is_bot=False,
        )
        bot_user = ZulipUser(
            user_id=2,
            full_name="TestBot",
            email="bot@test.com",
            is_active=True,
            is_bot=True,
        )

        mock_client = Mock()
        mock_client.get_users.return_value = [active_user, bot_user]
        mock_get_client.return_value = mock_client

        result = list_users()

        assert len(result) == 1
        content = result[0].text
        assert "Zulip Users" in content
        assert "Active Users (1)" in content
        assert "John Doe" in content
        assert "Bots (1)" in content
        assert "TestBot" in content


class TestMCPPrompts:
    """Tests for MCP prompts (daily summary, morning briefing, catch-up)."""

    @patch("zulipchat_mcp.server.get_client")
    def test_daily_summary_prompt(self, mock_get_client):
        """Test daily summary prompt."""
        from zulipchat_mcp.server import daily_summary_prompt

        mock_summary = {
            "total_messages": 50,
            "streams": {
                "general": {
                    "message_count": 30,
                    "topics": {"topic1": 15, "topic2": 10, "topic3": 5},
                }
            },
            "top_senders": {"Alice": 20, "Bob": 15, "Carol": 10},
        }

        mock_client = Mock()
        mock_client.get_daily_summary.return_value = mock_summary
        mock_get_client.return_value = mock_client

        result = daily_summary_prompt(["general"], 24)

        assert len(result) == 1
        content = result[0].text
        assert "Zulip Daily Summary" in content
        assert "Total Messages**: 50" in content
        assert "Stream Activity" in content
        assert "Most Active Users" in content

    @patch("zulipchat_mcp.server.get_client")
    def test_morning_briefing_prompt(self, mock_get_client):
        """Test morning briefing prompt."""
        from zulipchat_mcp.server import morning_briefing_prompt

        mock_yesterday = {
            "total_messages": 25,
            "streams": {},
            "top_senders": {"Alice": 15},
        }
        mock_week = {
            "total_messages": 200,
            "streams": {
                "general": {"message_count": 100, "topics": {"deployment": 30}}
            },
            "top_senders": {},
        }

        mock_client = Mock()
        mock_client.get_daily_summary.side_effect = [mock_yesterday, mock_week]
        mock_get_client.return_value = mock_client

        result = morning_briefing_prompt(["general"])

        assert len(result) == 1
        content = result[0].text
        assert "Good Morning!" in content
        assert "Yesterday's Activity" in content
        assert "This Week" in content
        assert "Most Active Streams" in content

    @patch("zulipchat_mcp.server.get_client")
    def test_catch_up_prompt(self, mock_get_client):
        """Test catch-up prompt."""
        from zulipchat_mcp.server import catch_up_prompt

        mock_message = {
            "id": 1,
            "sender": "John",
            "email": "john@test.com",
            "timestamp": 1640995200,
            "content": "Important update!",
            "type": "stream",
            "stream": "general",
            "topic": "updates",
        }

        mock_client = Mock()
        mock_client.get_streams.return_value = [
            ZulipStream(
                stream_id=1, name="general", description="General", is_private=False
            )
        ]
        mock_client.get_messages_from_stream.return_value = [mock_message]
        mock_get_client.return_value = mock_client

        result = catch_up_prompt(None, 4)

        assert len(result) == 1
        content = result[0].text
        assert "Quick Catch-Up" in content
        assert "general" in content
        assert "updates" in content
        assert "John" in content

    def test_catch_up_prompt_invalid_hours(self):
        """Test catch-up prompt with invalid hours."""
        from zulipchat_mcp.server import catch_up_prompt

        result = catch_up_prompt(["general"], 30)  # Max is 24

        assert len(result) == 1
        assert "hours must be between 1 and 24" in result[0].text


class TestSecurityFunctions:
    """Test security validation functions."""

    def test_sanitize_input_comprehensive(self):
        """Test comprehensive input sanitization."""
        from zulipchat_mcp.server import sanitize_input

        # Test HTML escaping
        result = sanitize_input("<script>alert('xss')</script>")
        assert "&lt;" in result and "&gt;" in result

        # Test backtick removal
        result = sanitize_input("Some `code` here")
        assert "`" not in result

        # Test length limiting
        long_input = "a" * 15000
        result = sanitize_input(long_input, max_length=1000)
        assert len(result) == 1000

    def test_validate_stream_name_comprehensive(self):
        """Test comprehensive stream name validation."""
        from zulipchat_mcp.server import validate_stream_name

        # Valid names
        assert validate_stream_name("general")
        assert validate_stream_name("team-updates")
        assert validate_stream_name("project_alpha")
        assert validate_stream_name("General Discussion")

        # Invalid names
        assert not validate_stream_name("")
        assert not validate_stream_name("a" * 101)  # Too long
        assert not validate_stream_name("test<script>")  # HTML
        assert not validate_stream_name("test@#$%")  # Special chars

    def test_validate_topic_comprehensive(self):
        """Test comprehensive topic validation."""
        from zulipchat_mcp.server import validate_topic

        # Valid topics
        assert validate_topic("Bug fixes")
        assert validate_topic("Feature request (important)")
        assert validate_topic("Daily standup, Jan 15")

        # Invalid topics
        assert not validate_topic("")
        assert not validate_topic("a" * 201)  # Too long
        assert not validate_topic("topic<script>")  # HTML

    def test_validate_emoji_comprehensive(self):
        """Test comprehensive emoji validation."""
        from zulipchat_mcp.security import validate_emoji

        # Valid emojis
        assert validate_emoji("thumbs_up")
        assert validate_emoji("heart")
        assert validate_emoji("fire123")

        # Invalid emojis
        assert not validate_emoji("")
        assert not validate_emoji("a" * 51)  # Too long
        assert not validate_emoji("emoji<script>")  # HTML
        assert not validate_emoji("emoji-with-dash")  # Dashes not allowed


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""

    @patch("zulipchat_mcp.server.get_client")
    def test_connection_errors_handled(self, mock_get_client):
        """Test that ConnectionError exceptions are handled properly."""
        from zulipchat_mcp.server import get_messages

        mock_client = Mock()
        mock_client.get_messages_from_stream.side_effect = ConnectionError(
            "Network error"
        )
        mock_get_client.return_value = mock_client

        result = get_messages("general")

        assert len(result) == 1
        assert "error" in result[0]
        assert "Failed to retrieve messages" in result[0]["error"]

    @patch("zulipchat_mcp.server.get_client")
    def test_validation_errors_handled(self, mock_get_client):
        """Test that ValidationError exceptions are handled properly."""
        from zulipchat_mcp.server import send_message

        mock_client = Mock()
        mock_client.send_message.side_effect = ValidationError("Invalid input")
        mock_get_client.return_value = mock_client

        result = send_message("stream", "general", "Hello!", "topic")

        assert result["status"] == "error"
        assert "error" in result

    @patch("zulipchat_mcp.server.get_client")
    def test_unexpected_errors_handled(self, mock_get_client):
        """Test that unexpected exceptions are handled gracefully."""
        from zulipchat_mcp.server import get_streams

        mock_client = Mock()
        mock_client.get_streams.side_effect = Exception("Unexpected error")
        mock_get_client.return_value = mock_client

        result = get_streams()

        assert len(result) == 1
        assert "error" in result[0]
        assert "An unexpected error occurred" in result[0]["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
