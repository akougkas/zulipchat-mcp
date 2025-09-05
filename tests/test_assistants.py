"""Tests for simplified assistant implementations in assistants.py.

These tests focus on the ACTUAL simplified code that's in production:
- Basic keyword extraction (not ML)
- Simple reply suggestions (not semantic analysis)
- Message counting summaries (not complex analysis)
- Basic keyword search (not semantic search)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.assistants import (
    auto_summarize_impl,
    extract_keywords,
    get_async_client,
    sanitize_input,
    smart_reply_impl,
    smart_search_impl,
    validate_stream_name,
)
from src.zulipchat_mcp.client import ZulipMessage
from src.zulipchat_mcp.exceptions import ZulipMCPError


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        ZulipMessage(
            id=1,
            content="The deployment failed with error code 500",
            sender_full_name="Alice Johnson",
            sender_email="alice@example.com",
            timestamp=1640995200,
            stream_name="general",
            subject="deployment-issues",
            type="stream"
        ),
        ZulipMessage(
            id=2,
            content="We need to rollback the deployment immediately",
            sender_full_name="Bob Smith",
            sender_email="bob@example.com",
            timestamp=1640995300,
            stream_name="general",
            subject="deployment-issues",
            type="stream"
        ),
        ZulipMessage(
            id=3,
            content="Rolling back now, will investigate the error logs",
            sender_full_name="Carol Davis",
            sender_email="carol@example.com",
            timestamp=1640995400,
            stream_name="general",
            subject="deployment-issues",
            type="stream"
        )
    ]


class TestKeywordExtraction:
    """Test the simplified keyword extraction functionality."""

    def test_extract_keywords_function(self):
        """Test basic keyword extraction from messages."""
        messages = [
            ZulipMessage(id=1, content="The deployment failed", sender_full_name="Alice",
                        sender_email="alice@test.com", timestamp=123, stream_name="test",
                        subject="test", type="stream"),
            ZulipMessage(id=2, content="deployment error logs show issues", sender_full_name="Bob",
                        sender_email="bob@test.com", timestamp=124, stream_name="test",
                        subject="test", type="stream")
        ]

        keywords = extract_keywords(messages)
        assert "deployment" in keywords
        assert len(keywords) <= 5

    def test_extract_keywords_empty_messages(self):
        """Test keyword extraction with no messages."""
        keywords = extract_keywords([])
        assert keywords == []

    def test_extract_keywords_filters_common_words(self):
        """Test that common words are filtered out."""
        messages = [
            ZulipMessage(id=1, content="the and for are but not you all", sender_full_name="Alice",
                        sender_email="alice@test.com", timestamp=123, stream_name="test",
                        subject="test", type="stream"),
            ZulipMessage(id=2, content="the and for are but not you all", sender_full_name="Bob",
                        sender_email="bob@test.com", timestamp=124, stream_name="test",
                        subject="test", type="stream")
        ]

        keywords = extract_keywords(messages)
        common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all'}
        assert not any(word in common_words for word in keywords)


class TestInputValidation:
    """Test input validation functions."""

    def test_validate_stream_name_valid(self):
        """Test valid stream names."""
        assert validate_stream_name("general")
        assert validate_stream_name("team-updates")
        assert validate_stream_name("project_alpha")
        assert validate_stream_name("General Discussion")

    def test_validate_stream_name_invalid(self):
        """Test invalid stream names."""
        assert not validate_stream_name("")  # Empty
        assert not validate_stream_name("a" * 101)  # Too long
        assert not validate_stream_name("stream<script>alert()</script>")  # Injection
        assert not validate_stream_name("stream@#$%")  # Invalid characters

    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        result = sanitize_input("Hello world")
        assert result == "Hello world"

    def test_sanitize_input_html_escape(self):
        """Test HTML escaping."""
        result = sanitize_input("<script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result

    def test_sanitize_input_removes_backticks(self):
        """Test backtick removal."""
        result = sanitize_input("Some `code` here")
        assert "`" not in result

    def test_sanitize_input_length_limit(self):
        """Test length limiting."""
        long_string = "a" * 20000
        result = sanitize_input(long_string, max_length=100)
        assert len(result) == 100


@pytest.mark.asyncio
class TestSmartReplySimplified:
    """Test the simplified smart reply implementation (no ML)."""

    async def test_smart_reply_impl_basic_suggestions(self, sample_messages):
        """Test simplified smart reply generates basic suggestions."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_messages_async.return_value = sample_messages
            mock_get_client.return_value = mock_client

            result = await smart_reply_impl("general", "deployment-issues", 4, 10)

            assert result["status"] == "success"
            assert len(result["suggestions"]) <= 5
            assert "deployment" in result["keywords"] or "rollback" in result["keywords"]
            assert result["message_count"] == 3

            # Verify it uses simple suggestions, not ML
            suggestions = result["suggestions"]
            assert any("Thanks" in s for s in suggestions) or any("look into" in s for s in suggestions)

    async def test_smart_reply_impl_empty_stream(self):
        """Test smart reply with no messages."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_messages_async.return_value = []
            mock_get_client.return_value = mock_client

            result = await smart_reply_impl("empty-stream", None, 4, 10)

            assert result["status"] == "success"
            assert "Start a new conversation" in result["suggestions"][0]
            assert result["context"]["message_count"] == 0
            assert result["context"]["participants"] == []

    async def test_smart_reply_impl_validation_errors(self):
        """Test input validation in smart reply."""
        # Invalid stream name
        result = await smart_reply_impl("invalid<script>", None, 4, 10)
        assert result["status"] == "error"
        assert "Invalid stream name" in result["error"]

        # Invalid hours_back
        result = await smart_reply_impl("general", None, 25, 10)
        assert result["status"] == "error"
        assert "hours_back must be between" in result["error"]

        # Invalid context_messages
        result = await smart_reply_impl("general", None, 4, 100)
        assert result["status"] == "error"
        assert "context_messages must be between" in result["error"]

    async def test_smart_reply_impl_error_handling(self):
        """Test error handling in smart reply."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_messages_async.side_effect = Exception("API Error")
            mock_get_client.return_value = mock_client

            result = await smart_reply_impl("general", None, 4, 10)

            assert result["status"] == "error"
            assert "Failed to generate reply suggestions" in result["error"]


@pytest.mark.asyncio
class TestAutoSummarizeSimplified:
    """Test the simplified auto summarize implementation (no ML)."""

    async def test_auto_summarize_impl_message_counting(self, sample_messages):
        """Test simplified summarization counts messages."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_messages_async.return_value = sample_messages
            mock_get_client.return_value = mock_client

            result = await auto_summarize_impl("general", "deployment-issues", 24, "standard", 100)

            assert result["status"] == "success"
            assert result["message_count"] == 3
            assert "Found 3 messages" in result["summary"]
            assert len(result["participants"]) == 3
            assert "Alice Johnson" in result["participants"]
            assert "Bob Smith" in result["participants"]
            assert "Carol Davis" in result["participants"]

    async def test_auto_summarize_impl_no_messages(self):
        """Test summarization with no messages."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_messages_async.return_value = []
            mock_get_client.return_value = mock_client

            result = await auto_summarize_impl("general", "empty-topic", 24, "standard", 100)

            assert result["status"] == "success"
            assert "No messages found" in result["summary"]
            assert result["message_count"] == 0
            assert result["participants"] == []
            assert result["key_points"] == []

    async def test_auto_summarize_impl_validation(self):
        """Test input validation in auto summarize."""
        # Invalid summary type
        result = await auto_summarize_impl("general", None, 24, "invalid", 100)
        assert result["status"] == "error"
        assert "summary_type must be" in result["error"]

        # Invalid hours_back
        result = await auto_summarize_impl("general", None, 200, "standard", 100)
        assert result["status"] == "error"
        assert "hours_back must be between" in result["error"]

        # Invalid max_messages
        result = await auto_summarize_impl("general", None, 24, "standard", 5)
        assert result["status"] == "error"
        assert "max_messages must be between" in result["error"]

    async def test_auto_summarize_impl_includes_metadata(self, sample_messages):
        """Test that summary includes proper metadata."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_messages_async.return_value = sample_messages
            mock_get_client.return_value = mock_client

            result = await auto_summarize_impl("general", "test-topic", 24, "detailed", 100)

            assert result["stream"] == "general"
            assert result["topic_filter"] == "test-topic"
            assert result["time_period"] == "24 hours"
            assert "generated_at" in result


@pytest.mark.asyncio
class TestSmartSearchSimplified:
    """Test the simplified smart search implementation (no semantic search)."""

    async def test_smart_search_impl_keyword_matching(self, sample_messages):
        """Test simplified search does basic keyword matching."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.search_messages_async.return_value = sample_messages
            mock_get_client.return_value = mock_client

            result = await smart_search_impl("deployment", "general", 168, 20)

            assert result["status"] == "success"
            assert result["statistics"]["total_results"] == 3
            assert result["query_analysis"]["search_type"] == "keyword"
            assert all(r["search_type"] == "keyword_search" for r in result["results"])

            # Check that results include proper message data
            first_result = result["results"][0]
            assert "message" in first_result
            assert "relevance_score" in first_result
            assert "matched_terms" in first_result

    async def test_smart_search_impl_empty_results(self):
        """Test search with no results."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.search_messages_async.return_value = []
            mock_get_client.return_value = mock_client

            result = await smart_search_impl("nonexistent", None, 168, 20)

            assert result["status"] == "success"
            assert result["statistics"]["total_results"] == 0
            assert result["results"] == []

    async def test_smart_search_impl_validation(self):
        """Test input validation in smart search."""
        # Empty query
        result = await smart_search_impl("", None, 168, 20)
        assert result["status"] == "error"
        assert "Query must be at least 2 characters" in result["error"]

        # Query too short
        result = await smart_search_impl("a", None, 168, 20)
        assert result["status"] == "error"
        assert "Query must be at least 2 characters" in result["error"]

        # Invalid hours_back
        result = await smart_search_impl("test", None, 1000, 20)
        assert result["status"] == "error"
        assert "hours_back must be between" in result["error"]

        # Invalid limit
        result = await smart_search_impl("test", None, 168, 100)
        assert result["status"] == "error"
        assert "limit must be between" in result["error"]

    async def test_smart_search_impl_handles_api_errors(self):
        """Test error handling when search API fails."""
        with patch('src.zulipchat_mcp.assistants.get_async_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.search_messages_async.side_effect = Exception("Search API failed")
            mock_get_client.return_value = mock_client

            result = await smart_search_impl("test", None, 168, 20)

            # Should handle gracefully and return empty results
            assert result["status"] == "success"
            assert result["results"] == []


class TestAsyncClientManagement:
    """Test async client management functions."""

    @patch('src.zulipchat_mcp.assistants.AsyncZulipClient')
    @patch('src.zulipchat_mcp.assistants.ConfigManager')
    def test_get_async_client_creates_instance(self, mock_config_manager, mock_async_client):
        """Test that get_async_client creates a new instance when needed."""
        # Reset global state
        import src.zulipchat_mcp.assistants as assistants_module
        assistants_module._async_client = None
        assistants_module._config = None

        mock_config_instance = MagicMock()
        mock_config_instance.validate_config.return_value = True
        mock_config_instance.config = MagicMock()
        mock_config_manager.return_value = mock_config_instance

        get_async_client()

        mock_config_manager.assert_called_once()
        mock_config_instance.validate_config.assert_called_once()
        mock_async_client.assert_called_once_with(mock_config_instance.config)

    @patch('src.zulipchat_mcp.assistants.ConfigManager')
    def test_get_async_client_invalid_config_raises_error(self, mock_config_manager):
        """Test that invalid config raises ZulipMCPError."""
        # Reset global state
        import src.zulipchat_mcp.assistants as assistants_module
        assistants_module._async_client = None
        assistants_module._config = None

        mock_config_instance = MagicMock()
        mock_config_instance.validate_config.return_value = False
        mock_config_manager.return_value = mock_config_instance

        with pytest.raises(ZulipMCPError, match="Invalid Zulip configuration"):
            get_async_client()
