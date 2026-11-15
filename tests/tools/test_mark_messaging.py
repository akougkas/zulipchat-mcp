"""Comprehensive tests for tools/mark_messaging.py.

Covers all functions including edge cases, error handling, and the registration function.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.mark_messaging import (
    update_message_flags_for_narrow,
)


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
            patch(
                "src.zulipchat_mcp.tools.mark_messaging.get_client"
            ) as mock_get_client,
        ):
            mock_get_client.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_update_flags_success_full_response(self, mock_deps):
        """Test successful flag update with all response fields."""
        narrow = [{"operator": "channel", "operand": "general"}]
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

        result = await update_message_flags_for_narrow(narrow=[], op="add", flag="read")

        assert result["status"] == "error"
        assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_update_flags_minimal_response(self, mock_deps):
        """Test handling of minimal API response (missing optional fields)."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
        }

        result = await update_message_flags_for_narrow(narrow=[], op="add", flag="read")

        assert result["status"] == "success"
        assert result["processed_count"] == 0
        assert result["updated_count"] == 0
        assert result["first_processed_id"] is None
        assert result["last_processed_id"] is None
        assert result["found_oldest"] is False
        assert result["found_newest"] is False
