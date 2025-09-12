"""Tests for consolidated messaging tools v2.5.0."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from zulipchat_mcp.core import IdentityType, ValidationMode
from zulipchat_mcp.tools.messaging_v25 import (
    bulk_operations,
    edit_message,
    message,
    search_messages,
    _convert_narrow_to_api_format,
    _truncate_content,
    MAX_CONTENT_SIZE,
)


class TestUtilityFunctions:
    """Test utility functions for messaging tools."""
    
    def test_truncate_content_normal(self) -> None:
        """Test content truncation with normal content."""
        content = "This is a normal message"
        result = _truncate_content(content)
        assert result == content
    
    def test_truncate_content_large(self, large_content: str) -> None:
        """Test content truncation with large content."""
        result = _truncate_content(large_content)
        
        assert len(result) <= MAX_CONTENT_SIZE + 50  # Allow for truncation message
        assert result.endswith("[Content truncated]")
        assert result.startswith("Large content")
    
    def test_convert_narrow_to_api_format(self, sample_narrow_filters: list[dict[str, str]]) -> None:
        """Test converting narrow filters to API format."""
        from zulipchat_mcp.core import NarrowFilter, NarrowOperator
        
        # Mix of dict and NarrowFilter objects
        narrow_filters = [
            sample_narrow_filters[0],  # Dict format
            NarrowFilter(NarrowOperator.TOPIC, "test-topic"),  # NarrowFilter object
        ]
        
        result = _convert_narrow_to_api_format(narrow_filters)
        
        assert len(result) == 2
        assert all(isinstance(f, dict) for f in result)
        assert result[0] == sample_narrow_filters[0]
        assert result[1] == {"operator": "topic", "operand": "test-topic"}


class TestMessageTool:
    """Test message() tool functionality."""
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_message_send_stream_basic(self, mock_managers) -> None:
        """Test sending basic stream message."""
        # Mock managers
        mock_config = Mock()
        mock_identity = Mock()
        mock_validator = Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        # Mock validator
        mock_validator.suggest_mode.return_value = ValidationMode.BASIC
        mock_validator.validate_tool_params.return_value = {
            "operation": "send",
            "type": "stream",
            "to": "general",
            "content": "Hello world!",
            "topic": "greetings",
            "read_by_sender": True,
        }
        
        # Mock execute_with_identity
        async def mock_execute(tool, params, func, identity=None):
            # Simulate successful API response
            return {
                "status": "success",
                "message_id": 12345,
                "operation": "send",
                "timestamp": "2024-01-15T14:30:00Z",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await message(
            operation="send",
            type="stream",
            to="general",
            content="Hello world!",
            topic="greetings",
        )
        
        assert result["status"] == "success"
        assert result["message_id"] == 12345
        assert result["operation"] == "send"
        mock_identity.execute_with_identity.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_message_send_private(self, mock_managers) -> None:
        """Test sending private message."""
        # Mock setup
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.BASIC
        mock_validator.validate_tool_params.return_value = {
            "operation": "send",
            "type": "private",
            "to": ["user@example.com"],
            "content": "Private message",
            "read_by_sender": True,
        }
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "message_id": 12346,
                "operation": "send",
                "timestamp": "2024-01-15T14:30:00Z",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await message(
            operation="send",
            type="private",
            to=["user@example.com"],
            content="Private message",
        )
        
        assert result["status"] == "success"
        assert result["message_id"] == 12346
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_message_schedule(self, mock_managers) -> None:
        """Test scheduling message."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.ADVANCED
        mock_validator.validate_tool_params.return_value = {
            "operation": "schedule",
            "type": "stream",
            "to": "announcements",
            "content": "Scheduled announcement",
            "topic": "meetings",
            "schedule_at": datetime(2024, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
        }
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "operation": "schedule",
                "scheduled_at": "2024-01-20T10:00:00+00:00",
                "message": "Scheduled message created (placeholder implementation)",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await message(
            operation="schedule",
            type="stream",
            to="announcements",
            content="Scheduled announcement",
            topic="meetings",
            schedule_at=datetime(2024, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "schedule"
        assert "scheduled_at" in result
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_message_draft(self, mock_managers) -> None:
        """Test creating draft message."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.BASIC
        mock_validator.validate_tool_params.return_value = {
            "operation": "draft",
            "type": "stream",
            "to": "general",
            "content": "Draft message",
            "topic": "drafts",
        }
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "operation": "draft",
                "draft_id": "draft_1642258200.123",
                "message": "Draft message created",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await message(
            operation="draft",
            type="stream",
            to="general",
            content="Draft message",
            topic="drafts",
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "draft"
        assert "draft_id" in result
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_message_validation_errors(self, mock_managers) -> None:
        """Test message validation errors."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.BASIC
        mock_validator.validate_tool_params.return_value = {}
        
        # Missing topic for stream message
        result = await message(
            operation="send",
            type="stream",
            to="general",
            content="Test message",
            # topic missing
        )
        
        assert result["status"] == "error"
        assert "Topic is required" in result["error"]
        
        # Missing schedule_at for scheduled message
        result = await message(
            operation="schedule",
            type="stream",
            to="general",
            content="Test message",
            topic="test",
            # schedule_at missing
        )
        
        assert result["status"] == "error"
        assert "schedule_at is required" in result["error"]
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_message_advanced_parameters(self, mock_managers) -> None:
        """Test message with advanced parameters."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.ADVANCED
        mock_validator.validate_tool_params.return_value = {
            "operation": "send",
            "type": "stream",
            "to": "general",
            "content": "Test message with code",
            "topic": "programming",
            "syntax_highlight": True,
            "link_preview": False,
            "emoji_translate": True,
        }
        
        async def mock_execute(tool, params, func, identity=None):
            return {"status": "success", "message_id": 12347}
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await message(
            operation="send",
            type="stream",
            to="general",
            content="Test message with code",
            topic="programming",
            syntax_highlight=True,
            link_preview=False,
            emoji_translate=True,
        )
        
        assert result["status"] == "success"
        mock_validator.suggest_mode.assert_called_once()
        # Verify advanced mode was suggested due to advanced parameters
        call_args = mock_validator.suggest_mode.call_args[0]
        params_dict = call_args[1]
        assert params_dict["syntax_highlight"] is True
        assert params_dict["link_preview"] is False


class TestSearchMessagesTool:
    """Test search_messages() tool functionality."""
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_search_messages_basic(self, mock_managers, sample_messages: list[dict[str, Any]]) -> None:
        """Test basic message search."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.BASIC
        mock_validator.validate_tool_params.return_value = {
            "narrow": [{"operator": "stream", "operand": "general"}],
            "anchor": "newest",
            "num_before": 50,
            "num_after": 50,
        }
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "messages": sample_messages,
                "count": len(sample_messages),
                "anchor": 12346,
                "found_anchor": True,
                "found_newest": True,
                "found_oldest": False,
                "history_limited": False,
                "narrow": [{"operator": "stream", "operand": "general"}],
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await search_messages(
            narrow=[{"operator": "stream", "operand": "general"}]
        )
        
        assert result["status"] == "success"
        assert len(result["messages"]) == len(sample_messages)
        assert result["count"] == len(sample_messages)
        assert "anchor" in result
        assert "narrow" in result
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_search_messages_with_narrow_builder(self, mock_managers) -> None:
        """Test search with NarrowBuilder filters."""
        from zulipchat_mcp.core import NarrowBuilder
        
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.ADVANCED
        mock_validator.validate_tool_params.return_value = {
            "narrow": [],  # Will be processed by the tool
            "anchor": "newest",
            "num_before": 50,
            "num_after": 0,
        }
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "messages": [],
                "count": 0,
                "anchor": "newest",
                "narrow": [],
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        # Build narrow filters
        narrow = (
            NarrowBuilder()
            .stream("development")
            .topic("bugs")
            .has("link")
            .search("critical")
            .build()
        )
        
        result = await search_messages(narrow=narrow)
        
        assert result["status"] == "success"
        mock_identity.execute_with_identity.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_search_messages_validation_errors(self, mock_managers) -> None:
        """Test search messages validation errors."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.BASIC
        mock_validator.validate_tool_params.return_value = {}
        
        # Invalid anchor
        result = await search_messages(anchor=-1)
        assert result["status"] == "error"
        assert "Invalid message ID" in result["error"]
        
        # Negative num_before
        result = await search_messages(num_before=-5)
        assert result["status"] == "error"
        assert "must be non-negative" in result["error"]
        
        # Too many messages requested
        result = await search_messages(num_before=3000, num_after=3000)
        assert result["status"] == "error"
        assert "Too many messages" in result["error"]
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_search_messages_advanced_options(self, mock_managers) -> None:
        """Test search messages with advanced options."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        mock_validator.suggest_mode.return_value = ValidationMode.ADVANCED
        mock_validator.validate_tool_params.return_value = {
            "narrow": [],
            "anchor": 12345,
            "num_before": 25,
            "num_after": 25,
            "include_anchor": False,
            "apply_markdown": False,
            "client_gravatar": True,
        }
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "messages": [],
                "count": 0,
                "anchor": 12345,
                "found_anchor": True,
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await search_messages(
            anchor=12345,
            num_before=25,
            num_after=25,
            include_anchor=False,
            apply_markdown=False,
            client_gravatar=True,
        )
        
        assert result["status"] == "success"


class TestEditMessageTool:
    """Test edit_message() tool functionality."""
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_edit_message_content(self, mock_managers) -> None:
        """Test editing message content."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "message": "Message edited successfully",
                "message_id": 12345,
                "changes": ["content"],
                "propagate_mode": "change_one",
                "timestamp": "2024-01-15T14:30:00Z",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await edit_message(
            message_id=12345,
            content="Updated message content",
        )
        
        assert result["status"] == "success"
        assert result["message_id"] == 12345
        assert "content" in result["changes"]
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_edit_message_topic(self, mock_managers) -> None:
        """Test editing message topic."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "message": "Message edited successfully",
                "message_id": 12345,
                "changes": ["topic"],
                "propagate_mode": "change_all",
                "timestamp": "2024-01-15T14:30:00Z",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await edit_message(
            message_id=12345,
            topic="updated-topic",
            propagate_mode="change_all",
        )
        
        assert result["status"] == "success"
        assert "topic" in result["changes"]
        assert result["propagate_mode"] == "change_all"
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_edit_message_move_stream(self, mock_managers) -> None:
        """Test moving message to different stream."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "message": "Message edited successfully",
                "message_id": 12345,
                "changes": ["stream"],
                "propagate_mode": "change_one",
                "timestamp": "2024-01-15T14:30:00Z",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await edit_message(
            message_id=12345,
            stream_id=67890,
            topic="moved-message",
        )
        
        assert result["status"] == "success"
        assert "stream" in result["changes"]
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_edit_message_validation_errors(self, mock_managers) -> None:
        """Test edit message validation errors."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        # Invalid message ID
        result = await edit_message(message_id=0, content="test")
        assert result["status"] == "error"
        assert "Invalid message ID" in result["error"]
        
        # No parameters to edit
        result = await edit_message(message_id=12345)
        assert result["status"] == "error"
        assert "Must provide content, topic, or stream_id" in result["error"]
        
        # Cannot update content and move stream simultaneously
        result = await edit_message(
            message_id=12345,
            content="new content",
            stream_id=67890,
        )
        assert result["status"] == "error"
        assert "Cannot update content and move stream simultaneously" in result["error"]
        
        # Invalid propagate mode
        result = await edit_message(
            message_id=12345,
            topic="new topic",
            propagate_mode="invalid_mode",
        )
        assert result["status"] == "error"
        assert "Invalid propagate_mode" in result["error"]


class TestBulkOperationsTool:
    """Test bulk_operations() tool functionality."""
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_bulk_mark_read_by_narrow(self, mock_managers) -> None:
        """Test bulk mark as read using narrow filters."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "message": "Successfully mark read",
                "affected_count": 15,
                "operation": "mark_read",
                "message_ids": [12345, 12346, 12347],
                "timestamp": "2024-01-15T14:30:00Z",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await bulk_operations(
            operation="mark_read",
            narrow=[{"operator": "stream", "operand": "general"}],
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "mark_read"
        assert result["affected_count"] == 15
        assert len(result["message_ids"]) == 3
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_bulk_add_flag_by_message_ids(self, mock_managers) -> None:
        """Test bulk add flag using message IDs."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "message": "Successfully add flag 'starred'",
                "affected_count": 3,
                "operation": "add_flag",
                "flag": "starred",
                "message_ids": [12345, 12346, 12347],
                "timestamp": "2024-01-15T14:30:00Z",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await bulk_operations(
            operation="add_flag",
            message_ids=[12345, 12346, 12347],
            flag="starred",
        )
        
        assert result["status"] == "success"
        assert result["operation"] == "add_flag"
        assert result["flag"] == "starred"
        assert result["affected_count"] == 3
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_bulk_operations_validation_errors(self, mock_managers) -> None:
        """Test bulk operations validation errors."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        # Missing selection (none of: simple params, narrow, or message_ids)
        result = await bulk_operations(operation="mark_read")
        assert result["status"] == "error"
        # Allow broader error copy as implementation evolved
        assert result["error"].startswith("Must provide")
        assert "message_ids" in result["error"]
        
        # Multiple selection methods provided (conflict)
        result = await bulk_operations(
            operation="mark_read",
            narrow=[{"operator": "stream", "operand": "general"}],
            message_ids=[12345],
        )
        assert result["status"] == "error"
        assert result["error"].startswith("Cannot specify")
        
        # Missing flag for flag operations
        result = await bulk_operations(
            operation="add_flag",
            message_ids=[12345],
        )
        assert result["status"] == "error"
        assert "Flag parameter is required" in result["error"]
    
    @pytest.mark.asyncio
    @patch('zulipchat_mcp.tools.messaging_v25._get_managers')
    async def test_bulk_operations_no_matches(self, mock_managers) -> None:
        """Test bulk operations with no matching messages."""
        mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
        mock_managers.return_value = (mock_config, mock_identity, mock_validator)
        
        async def mock_execute(tool, params, func, identity=None):
            return {
                "status": "success",
                "message": "No messages matched the criteria",
                "affected_count": 0,
                "operation": "mark_read",
            }
        
        mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
        
        result = await bulk_operations(
            operation="mark_read",
            narrow=[{"operator": "stream", "operand": "nonexistent"}],
        )
        
        assert result["status"] == "success"
        assert result["affected_count"] == 0
        assert "No messages matched" in result["message"]


class TestMessagingIntegration:
    """Integration tests for messaging tools."""
    
    @pytest.mark.asyncio
    async def test_message_search_edit_workflow(self) -> None:
        """Test complete workflow: send, search, edit message."""
        with (
            patch('zulipchat_mcp.tools.messaging_v25._get_managers') as mock_managers,
            patch('zulipchat_mcp.tools.messaging_v25.track_tool_call'),
            patch('zulipchat_mcp.tools.messaging_v25.track_message_sent'),
        ):
            # Mock managers
            mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
            mock_managers.return_value = (mock_config, mock_identity, mock_validator)
            
            mock_validator.suggest_mode.return_value = ValidationMode.BASIC
            mock_validator.validate_tool_params.return_value = {}
            
            # Step 1: Send message
            async def mock_send_execute(tool, params, func, identity=None):
                return {"status": "success", "message_id": 12345}
            
            mock_identity.execute_with_identity = AsyncMock(side_effect=mock_send_execute)
            
            send_result = await message(
                operation="send",
                type="stream",
                to="general",
                content="Original message",
                topic="test",
            )
            
            assert send_result["status"] == "success"
            message_id = send_result["message_id"]
            
            # Step 2: Search for the message
            async def mock_search_execute(tool, params, func, identity=None):
                return {
                    "status": "success",
                    "messages": [{
                        "id": message_id,
                        "content": "Original message",
                        "topic": "test",
                    }],
                    "count": 1,
                }
            
            mock_identity.execute_with_identity = AsyncMock(side_effect=mock_search_execute)
            
            search_result = await search_messages(
                narrow=[{"operator": "topic", "operand": "test"}]
            )
            
            assert search_result["status"] == "success"
            assert len(search_result["messages"]) == 1
            assert search_result["messages"][0]["id"] == message_id
            
            # Step 3: Edit the message
            async def mock_edit_execute(tool, params, func, identity=None):
                return {
                    "status": "success",
                    "message_id": message_id,
                    "changes": ["content"],
                }
            
            mock_identity.execute_with_identity = AsyncMock(side_effect=mock_edit_execute)
            
            edit_result = await edit_message(
                message_id=message_id,
                content="Updated message",
            )
            
            assert edit_result["status"] == "success"
            assert edit_result["message_id"] == message_id
            assert "content" in edit_result["changes"]
    
    @pytest.mark.asyncio
    async def test_concurrent_messaging_operations(self) -> None:
        """Test concurrent messaging operations."""
        with (
            patch('zulipchat_mcp.tools.messaging_v25._get_managers') as mock_managers,
            patch('zulipchat_mcp.tools.messaging_v25.track_tool_call'),
        ):
            # Mock setup
            mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
            mock_managers.return_value = (mock_config, mock_identity, mock_validator)
            
            mock_validator.suggest_mode.return_value = ValidationMode.BASIC
            mock_validator.validate_tool_params.return_value = {}
            
            call_count = 0
            
            async def mock_execute(tool, params, func, identity=None):
                nonlocal call_count
                call_count += 1
                this_call = call_count  # capture unique value per invocation
                await asyncio.sleep(0.01)  # Simulate API delay
                return {"status": "success", "message_id": 12340 + this_call}
            
            mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
            
            # Send multiple messages concurrently
            tasks = [
                message(
                    operation="send",
                    type="stream",
                    to="general",
                    content=f"Concurrent message {i}",
                    topic="concurrent-test",
                )
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All should succeed
            assert len(results) == 5
            assert all(r["status"] == "success" for r in results)
            assert len(set(r["message_id"] for r in results)) == 5  # Unique IDs
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self) -> None:
        """Test error handling and recovery in messaging tools."""
        with (
            patch('zulipchat_mcp.tools.messaging_v25._get_managers') as mock_managers,
            patch('zulipchat_mcp.tools.messaging_v25.track_tool_call'),
            patch('zulipchat_mcp.tools.messaging_v25.track_tool_error'),
        ):
            mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
            mock_managers.return_value = (mock_config, mock_identity, mock_validator)
            
            mock_validator.suggest_mode.return_value = ValidationMode.BASIC
            mock_validator.validate_tool_params.side_effect = Exception("Validation error")
            
            # Should handle validation errors gracefully
            result = await message(
                operation="send",
                type="stream",
                to="general",
                content="Test message",
                topic="test",
            )
            
            assert result["status"] == "error"
            assert "Failed to send message" in result["error"]
            assert result["operation"] == "send"
    
    @pytest.mark.asyncio
    async def test_parameter_mode_progression(self) -> None:
        """Test parameter validation mode progression."""
        with patch('zulipchat_mcp.tools.messaging_v25._get_managers') as mock_managers:
            mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
            mock_managers.return_value = (mock_config, mock_identity, mock_validator)
            
            # Test basic -> advanced -> expert progression
            test_cases = [
                # Basic mode
                {
                    "params": {
                        "operation": "send",
                        "type": "stream",
                        "to": "general",
                        "content": "Basic message",
                        "topic": "basic",
                    },
                    "expected_mode": ValidationMode.BASIC,
                },
                # Advanced mode
                {
                    "params": {
                        "operation": "send",
                        "type": "stream",
                        "to": "general",
                        "content": "Advanced message",
                        "topic": "advanced",
                        "syntax_highlight": True,
                        "link_preview": False,
                    },
                    "expected_mode": ValidationMode.ADVANCED,
                },
                # Expert mode
                {
                    "params": {
                        "operation": "send",
                        "type": "stream",
                        "to": "general",
                        "content": "Expert message",
                        "topic": "expert",
                        "queue_id": "queue-123",
                        "local_id": "local-456",
                    },
                    "expected_mode": ValidationMode.EXPERT,
                },
            ]
            
            for case in test_cases:
                mock_validator.reset_mock()
                mock_validator.suggest_mode.return_value = case["expected_mode"]
                mock_validator.validate_tool_params.return_value = case["params"]
                
                async def mock_execute(tool, params, func, identity=None):
                    return {"status": "success", "message_id": 12345}
                
                mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
                
                await message(**case["params"])
                
                # Verify correct mode was suggested
                mock_validator.suggest_mode.assert_called_once()
                call_args = mock_validator.suggest_mode.call_args[0]
                assert call_args[0] == "messaging.message"


class TestMessagingPerformance:
    """Performance tests for messaging tools."""
    
    @pytest.mark.asyncio
    async def test_large_content_handling(self, large_content: str, performance_monitor) -> None:
        """Test handling of large message content."""
        with patch('zulipchat_mcp.tools.messaging_v25._get_managers') as mock_managers:
            mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
            mock_managers.return_value = (mock_config, mock_identity, mock_validator)
            
            mock_validator.suggest_mode.return_value = ValidationMode.BASIC
            mock_validator.validate_tool_params.return_value = {}
            
            async def mock_execute(tool, params, func, identity=None):
                return {"status": "success", "message_id": 12345}
            
            mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
            
            performance_monitor.start()
            
            result = await message(
                operation="send",
                type="stream",
                to="general",
                content=large_content,
                topic="performance-test",
            )
            
            metrics = performance_monitor.stop()
            
            assert result["status"] == "success"
            # Should complete reasonably quickly even with large content
            assert metrics["duration_ms"] < 1000  # Less than 1 second
    
    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self, performance_monitor) -> None:
        """Test performance of bulk operations."""
        with patch('zulipchat_mcp.tools.messaging_v25._get_managers') as mock_managers:
            mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
            mock_managers.return_value = (mock_config, mock_identity, mock_validator)
            
            # Simulate bulk operation on many messages
            message_ids = list(range(1, 1001))  # 1000 messages
            
            async def mock_execute(tool, params, func, identity=None):
                return {
                    "status": "success",
                    "affected_count": len(message_ids),
                    "operation": "mark_read",
                }
            
            mock_identity.execute_with_identity = AsyncMock(side_effect=mock_execute)
            
            performance_monitor.start()
            
            result = await bulk_operations(
                operation="mark_read",
                message_ids=message_ids,
            )
            
            metrics = performance_monitor.stop()
            
            assert result["status"] == "success"
            assert result["affected_count"] == 1000
            # Bulk operations should be efficient
            assert metrics["duration_ms"] < 500  # Less than 0.5 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
