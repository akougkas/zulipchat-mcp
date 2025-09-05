"""Enhanced tests for the MCP server with security and error handling."""

import sys
sys.path.insert(0, 'src')

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from zulipchat_mcp.client import ZulipMessage, ZulipStream, ZulipUser


class TestEnhancedServerTools:
    """Test enhanced server tools with security."""
    
    @patch("zulipchat_mcp.server.get_client")
    def test_send_message_validation_errors(self, mock_get_client):
        """Test send_message validation errors."""
        from zulipchat_mcp.server import send_message
        
        # Test invalid message type
        result = send_message("invalid", "general", "test", "topic")
        assert result["status"] == "error"
        assert "Invalid message_type" in result["error"]
        
        # Test missing topic for stream message
        result = send_message("stream", "general", "test", None)
        assert result["status"] == "error"
        assert "Topic required" in result["error"]
        
        # Test invalid stream name
        result = send_message("stream", "stream$invalid", "test", "topic")
        assert result["status"] == "error"
        assert "Invalid stream name" in result["error"]
        
        # Test invalid topic
        result = send_message("stream", "general", "test", "topic$invalid")
        assert result["status"] == "error"
        assert "Invalid topic" in result["error"]
    
    @patch("zulipchat_mcp.server.get_client")
    def test_send_message_success_with_sanitization(self, mock_get_client):
        """Test successful message sending with content sanitization."""
        from zulipchat_mcp.server import send_message
        
        mock_client = Mock()
        mock_client.send_message.return_value = {"result": "success", "id": 123}
        mock_get_client.return_value = mock_client
        
        # Message with HTML content
        result = send_message(
            "stream", 
            "general", 
            "<script>alert('test')</script>Hello", 
            "test-topic"
        )
        
        assert result["status"] == "success"
        assert result["message_id"] == 123
        assert "timestamp" in result
        
        # Check that content was sanitized
        call_args = mock_client.send_message.call_args[0]
        assert "<script>" not in call_args[2]
    
    @patch("zulipchat_mcp.server.get_client")
    def test_get_messages_validation(self, mock_get_client):
        """Test get_messages validation."""
        from zulipchat_mcp.server import get_messages
        
        # Test invalid stream name
        result = get_messages(stream_name="stream@invalid")
        assert result[0]["error"] == "Invalid stream name: stream@invalid"
        
        # Test invalid topic
        result = get_messages(stream_name="general", topic="topic$invalid")
        assert result[0]["error"] == "Invalid topic: topic$invalid"
        
        # Test invalid hours_back
        result = get_messages(hours_back=200)
        assert "hours_back must be between 1 and 168" in result[0]["error"]
        
        # Test invalid limit
        result = get_messages(limit=200)
        assert "limit must be between 1 and 100" in result[0]["error"]
    
    @patch("zulipchat_mcp.server.get_client")
    def test_search_messages_validation(self, mock_get_client):
        """Test search_messages validation."""
        from zulipchat_mcp.server import search_messages
        
        # Test empty query
        result = search_messages("")
        assert "Query cannot be empty" in result[0]["error"]
        
        # Test invalid limit
        result = search_messages("test", limit=200)
        assert "limit must be between 1 and 100" in result[0]["error"]
    
    @patch("zulipchat_mcp.server.get_client")
    def test_add_reaction_validation(self, mock_get_client):
        """Test add_reaction validation."""
        from zulipchat_mcp.server import add_reaction
        
        # Test invalid message ID
        result = add_reaction(-1, "smile")
        assert result["status"] == "error"
        assert "Invalid message ID" in result["error"]
        
        # Test invalid emoji name
        result = add_reaction(123, "emoji-invalid")
        assert result["status"] == "error"
        assert "Invalid emoji name" in result["error"]
    
    @patch("zulipchat_mcp.server.get_client")
    def test_edit_message_validation(self, mock_get_client):
        """Test edit_message validation."""
        from zulipchat_mcp.server import edit_message
        
        # Test invalid message ID
        result = edit_message(0)
        assert result["status"] == "error"
        assert "Invalid message ID" in result["error"]
        
        # Test no content or topic provided
        result = edit_message(123)
        assert result["status"] == "error"
        assert "Must provide content or topic" in result["error"]
        
        # Test invalid topic
        result = edit_message(123, topic="topic$invalid")
        assert result["status"] == "error"
        assert "Invalid topic" in result["error"]
    
    @patch("zulipchat_mcp.server.get_client")
    def test_get_daily_summary_validation(self, mock_get_client):
        """Test get_daily_summary validation."""
        from zulipchat_mcp.server import get_daily_summary
        
        # Test invalid stream name
        result = get_daily_summary(streams=["stream@invalid"])
        assert result["status"] == "error"
        assert "Invalid stream name" in result["error"]
        
        # Test invalid hours_back
        result = get_daily_summary(hours_back=200)
        assert result["status"] == "error"
        assert "hours_back must be between 1 and 168" in result["error"]
    
    @patch("zulipchat_mcp.server.get_client")
    def test_error_handling(self, mock_get_client):
        """Test error handling in tools."""
        from zulipchat_mcp.server import send_message
        
        # Simulate client error
        mock_client = Mock()
        mock_client.send_message.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        
        result = send_message("stream", "general", "test", "topic")
        assert result["status"] == "error"
        assert result["error"] == "Internal server error"


class TestServerResources:
    """Test MCP resources."""
    
    @patch("zulipchat_mcp.server.get_client")
    def test_get_stream_messages_resource(self, mock_get_client):
        """Test stream messages resource."""
        from zulipchat_mcp.server import get_stream_messages
        
        # Test invalid stream name
        result = get_stream_messages("stream@invalid")
        assert len(result) == 1
        assert "Invalid stream name" in result[0].text
        
        # Test valid stream
        mock_message = ZulipMessage(
            id=1,
            sender_full_name="John Doe",
            sender_email="john@example.com",
            timestamp=1640995200,
            content="Test message",
            subject="test-topic",
            type="stream"
        )
        
        mock_client = Mock()
        mock_client.get_messages_from_stream.return_value = [mock_message]
        mock_get_client.return_value = mock_client
        
        result = get_stream_messages("general")
        assert len(result) == 1
        assert "Messages from #general" in result[0].text
        assert "John Doe" in result[0].text
    
    @patch("zulipchat_mcp.server.get_client")
    def test_list_streams_resource(self, mock_get_client):
        """Test list streams resource."""
        from zulipchat_mcp.server import list_streams
        
        mock_stream = ZulipStream(
            stream_id=1,
            name="general",
            description="General discussion",
            is_private=False
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
        """Test list users resource."""
        from zulipchat_mcp.server import list_users
        
        mock_user = ZulipUser(
            user_id=1,
            full_name="John Doe",
            email="john@example.com",
            is_active=True,
            is_bot=False
        )
        
        mock_bot = ZulipUser(
            user_id=2,
            full_name="Bot User",
            email="bot@example.com",
            is_active=True,
            is_bot=True
        )
        
        mock_client = Mock()
        mock_client.get_users.return_value = [mock_user, mock_bot]
        mock_get_client.return_value = mock_client
        
        result = list_users()
        assert len(result) == 1
        assert "Zulip Users" in result[0].text
        assert "John Doe" in result[0].text
        assert "Bot User" in result[0].text
        assert "Active Users (1)" in result[0].text
        assert "Bots (1)" in result[0].text


class TestServerPrompts:
    """Test MCP prompts."""
    
    @patch("zulipchat_mcp.server.get_client")
    def test_daily_summary_prompt_validation(self, mock_get_client):
        """Test daily summary prompt validation."""
        from zulipchat_mcp.server import daily_summary_prompt
        
        # Test invalid stream name
        result = daily_summary_prompt(streams=["stream@invalid"])
        assert len(result) == 1
        assert "Invalid stream name" in result[0].text
        
        # Test invalid hours
        result = daily_summary_prompt(hours=200)
        assert len(result) == 1
        assert "hours must be between 1 and 168" in result[0].text
    
    @patch("zulipchat_mcp.server.get_client")
    def test_morning_briefing_prompt_validation(self, mock_get_client):
        """Test morning briefing prompt validation."""
        from zulipchat_mcp.server import morning_briefing_prompt
        
        # Test invalid stream name
        result = morning_briefing_prompt(streams=["stream@invalid"])
        assert len(result) == 1
        assert "Invalid stream name" in result[0].text
    
    @patch("zulipchat_mcp.server.get_client")
    def test_catch_up_prompt_validation(self, mock_get_client):
        """Test catch-up prompt validation."""
        from zulipchat_mcp.server import catch_up_prompt
        
        # Test invalid stream name
        result = catch_up_prompt(streams=["stream@invalid"])
        assert len(result) == 1
        assert "Invalid stream name" in result[0].text
        
        # Test invalid hours
        result = catch_up_prompt(hours=30)
        assert len(result) == 1
        assert "hours must be between 1 and 24" in result[0].text