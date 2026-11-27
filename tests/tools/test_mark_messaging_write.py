"""Tests for write operations in tools/mark_messaging.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.mark_messaging import (
    update_message_flags_for_narrow,
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
            "updated_count": 5,
            "found_newest": True,
        }
        # Default successful stream resolution - now uses get_streams()
        client.get_streams.return_value = {
            "result": "success",
            "streams": [
                {"stream_id": 123, "name": "Test Stream"},
                {"stream_id": 456, "name": "Other Stream"},
            ],
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.get_client"
            ) as mock_get_client,
        ):
            mock_get_client.return_value = mock_client
            yield mock_client

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
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Invalid flag",
        }
        result = await update_message_flags_for_narrow(
            narrow=[], op="add", flag="invalid_flag"
        )
        assert result["status"] == "error"
        assert "Invalid flag" in result["error"]["message"]
