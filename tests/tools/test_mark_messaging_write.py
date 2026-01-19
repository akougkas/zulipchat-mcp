"""Tests for write operations in tools/mark_messaging.py."""

import pytest
from unittest.mock import MagicMock, patch
from src.zulipchat_mcp.tools.mark_messaging import (
    mark_stream_as_read,
    star_messages,
    update_message_flags_for_narrow,
    mark_all_as_read
)

class TestMessageFlags:
    """Tests for message flag operations."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {
            "result": "success",
            "processed_count": 10,
            "updated_count": 5
        }
        # Default successful stream resolution
        client.get_stream_id.return_value = {
            "result": "success",
            "stream": {"name": "Test Stream"}
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with patch("src.zulipchat_mcp.tools.mark_messaging.ConfigManager"), \
             patch("src.zulipchat_mcp.tools.mark_messaging.ZulipClientWrapper") as mock_wrapper:
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_mark_stream_as_read(self, mock_deps):
        """Test marking a stream as read."""
        result = await mark_stream_as_read(123)
        assert result["status"] == "success"
        assert result["operation"] == "add_read"
        
        # Verify call arguments
        mock_deps.client.call_endpoint.assert_called()
        args = mock_deps.client.call_endpoint.call_args
        assert args[0][0] == "messages/flags/narrow"
        assert args[1]["method"] == "POST"
        request = args[1]["request"]
        assert request["flag"] == "read"
        assert request["op"] == "add"
        # Should now use stream NAME resolved from ID
        assert request["narrow"] == [{"operator": "stream", "operand": "Test Stream"}]

    @pytest.mark.asyncio
    async def test_mark_nonexistent_stream(self, mock_deps):
        """Test marking a nonexistent stream (validation error)."""
        # Mock get_stream_id failure
        mock_deps.get_stream_id.return_value = {"result": "error", "msg": "Invalid stream"}
        
        result = await mark_stream_as_read(999)
        assert result["status"] == "error"
        # Expect the validation error from _resolve_stream_name
        assert "Unknown stream ID: 999" in result["error"]

    @pytest.mark.asyncio
    async def test_star_messages_by_narrow(self, mock_deps):
        """Test starring messages using a narrow."""
        narrow = [{"operator": "is", "operand": "private"}]
        result = await star_messages(narrow=narrow)
        assert result["status"] == "success"
        assert result["operation"] == "add_starred"
        
        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["flag"] == "starred"
        assert request["narrow"] == narrow

    @pytest.mark.asyncio
    async def test_star_empty_narrow(self, mock_deps):
        """Test starring with empty/missing criteria."""
        result = await star_messages()
        assert result["status"] == "error"
        assert "Must provide narrow" in result["error"]

    @pytest.mark.asyncio
    async def test_mark_all_as_read_large_volume(self, mock_deps):
        """Test marking all messages as read (checks num_after param)."""
        result = await mark_all_as_read()
        assert result["status"] == "success"
        
        args = mock_deps.client.call_endpoint.call_args
        request = args[1]["request"]
        assert request["narrow"] == []  # Empty narrow for "all"
        assert request["num_after"] == 1000

    @pytest.mark.asyncio
    async def test_flag_operation_add(self, mock_deps):
        """Test explicitly adding a flag."""
        result = await update_message_flags_for_narrow(
            narrow=[], op="add", flag="collapsed"
        )
        assert result["status"] == "success"
        assert result["operation"] == "add_collapsed"

    @pytest.mark.asyncio
    async def test_flag_operation_remove(self, mock_deps):
        """Test explicitly removing a flag."""
        result = await update_message_flags_for_narrow(
            narrow=[], op="remove", flag="read"
        )
        assert result["status"] == "success"
        assert result["operation"] == "remove_read"

    @pytest.mark.asyncio
    async def test_invalid_flag_name(self, mock_deps):
        """Test with an invalid flag name (backend rejection)."""
        mock_deps.client.call_endpoint.return_value = {"result": "error", "msg": "Invalid flag"}
        result = await update_message_flags_for_narrow(
            narrow=[], op="add", flag="invalid_flag"
        )
        assert result["status"] == "error"
        assert "Invalid flag" in result["error"]

