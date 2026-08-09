"""Tests for tools/drafts.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.drafts import (
    create_draft,
    delete_draft,
    edit_draft,
    get_drafts,
)


class TestDrafts:
    """Tests for draft operations."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.client.call_endpoint.return_value = {"result": "success"}
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with patch("src.zulipchat_mcp.tools.drafts.get_client") as mock_get_client:
            mock_get_client.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_get_drafts(self, mock_deps):
        """Test getting the current user's drafts."""
        drafts = [
            {
                "id": 1,
                "type": "stream",
                "to": [42],
                "topic": "planning",
                "content": "Next steps",
                "timestamp": 1595479019,
            }
        ]
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "drafts": drafts,
            "count": 1,
        }

        result = await get_drafts()

        assert result == {"status": "success", "drafts": drafts, "count": 1}
        mock_deps.client.call_endpoint.assert_called_once_with(
            "drafts", method="GET", request={}
        )

    @pytest.mark.asyncio
    async def test_get_drafts_api_error(self, mock_deps):
        """Test an API error while getting drafts."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Drafts are unavailable",
        }

        result = await get_drafts()

        assert result == {"status": "error", "error": "Drafts are unavailable"}

    @pytest.mark.asyncio
    async def test_create_stream_draft(self, mock_deps):
        """Test creating a channel draft with the required wire encoding."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "ids": [17],
        }

        result = await create_draft(
            type="stream",
            to=[42],
            topic="planning",
            content="Next steps",
            timestamp=1595479019,
        )

        assert result == {"status": "success", "draft_id": 17}
        call = mock_deps.client.call_endpoint.call_args
        assert call.args == ("drafts",)
        assert call.kwargs["method"] == "POST"
        assert json.loads(call.kwargs["request"]["drafts"]) == [
            {
                "type": "stream",
                "to": [42],
                "topic": "planning",
                "content": "Next steps",
                "timestamp": 1595479019,
            }
        ]
        mock_deps.get_stream_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_stream_draft_resolves_name(self, mock_deps):
        mock_deps.get_stream_id.return_value = {
            "result": "success",
            "stream_id": 538778,
        }
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "ids": [17],
        }

        result = await create_draft(
            type="stream",
            to="sandbox",
            topic="planning",
            content="Next steps",
        )

        assert result == {"status": "success", "draft_id": 17}
        mock_deps.get_stream_id.assert_called_once_with("sandbox")
        request = mock_deps.client.call_endpoint.call_args.kwargs["request"]
        assert json.loads(request["drafts"])[0]["to"] == [538778]

    @pytest.mark.asyncio
    async def test_create_private_draft_resolves_names_and_keeps_ids(self, mock_deps):
        with patch(
            "src.zulipchat_mcp.tools.drafts.resolve_user_identifier",
            new_callable=AsyncMock,
            return_value={"user_id": 7},
        ) as resolver:
            result = await create_draft(
                type="private",
                to=["Alice", 8],
                content="Hello",
            )

        assert result["status"] == "success"
        resolver.assert_awaited_once_with("Alice", mock_deps)
        request = mock_deps.client.call_endpoint.call_args.kwargs["request"]
        assert json.loads(request["drafts"])[0]["to"] == [7, 8]

    @pytest.mark.asyncio
    async def test_create_draft_api_error(self, mock_deps):
        """Test an API error while creating a draft."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Invalid draft",
        }

        result = await create_draft(type="private", to=[7], topic="", content="Hello")

        assert result == {"status": "error", "error": "Invalid draft"}

    @pytest.mark.asyncio
    async def test_create_stream_draft_requires_topic(self, mock_deps):
        """Test local topic validation for channel drafts."""
        result = await create_draft(type="stream", to=[42], content="No topic")

        assert result == {
            "status": "error",
            "error": "Topic required for stream drafts",
        }
        mock_deps.client.call_endpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_stream_draft_requires_one_channel(self, mock_deps):
        """Test local channel target validation for channel drafts."""
        result = await create_draft(
            type="stream", to=[42, 43], topic="planning", content="Too many"
        )

        assert result == {
            "status": "error",
            "error": "Stream drafts must specify exactly one channel",
        }
        mock_deps.client.call_endpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_draft(self, mock_deps):
        """Test editing a draft with the required wire encoding."""
        result = await edit_draft(
            draft_id=17,
            type="private",
            to=[7, 8],
            topic="",
            content="Updated content",
        )

        assert result == {"status": "success", "draft_id": 17, "action": "edited"}
        call = mock_deps.client.call_endpoint.call_args
        assert call.args == ("drafts/17",)
        assert call.kwargs["method"] == "PATCH"
        assert json.loads(call.kwargs["request"]["draft"]) == {
            "type": "private",
            "to": [7, 8],
            "topic": "",
            "content": "Updated content",
        }

    @pytest.mark.asyncio
    async def test_edit_private_draft_resolves_scalar_name(self, mock_deps):
        with patch(
            "src.zulipchat_mcp.tools.drafts.resolve_user_identifier",
            new_callable=AsyncMock,
            return_value={"user_id": 7},
        ):
            result = await edit_draft(
                draft_id=17,
                type="private",
                to="Alice",
                content="Updated content",
            )

        assert result["status"] == "success"
        request = mock_deps.client.call_endpoint.call_args.kwargs["request"]
        assert json.loads(request["draft"])["to"] == [7]

    @pytest.mark.asyncio
    async def test_unknown_stream_returns_resolution_error(self, mock_deps):
        mock_deps.get_stream_id.return_value = {
            "result": "error",
            "msg": "Unknown stream",
        }

        result = await create_draft(
            type="stream",
            to="missing",
            topic="planning",
            content="Hello",
        )

        assert result == {"status": "error", "error": "Unknown stream"}
        mock_deps.client.call_endpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_draft_api_error(self, mock_deps):
        """Test editing a draft that does not exist."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Draft does not exist",
        }

        result = await edit_draft(
            draft_id=99,
            type="private",
            to=[7],
            topic="",
            content="Updated content",
        )

        assert result == {"status": "error", "error": "Draft does not exist"}

    @pytest.mark.asyncio
    async def test_edit_stream_draft_requires_topic(self, mock_deps):
        """Test local topic validation when editing a channel draft."""
        result = await edit_draft(
            draft_id=17,
            type="stream",
            to=[42],
            content="No topic",
        )

        assert result["status"] == "error"
        assert "Topic required" in result["error"]
        mock_deps.client.call_endpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_draft(self, mock_deps):
        """Test deleting a draft."""
        result = await delete_draft(17)

        assert result == {"status": "success", "draft_id": 17, "action": "deleted"}
        mock_deps.client.call_endpoint.assert_called_once_with(
            "drafts/17", method="DELETE", request={}
        )

    @pytest.mark.asyncio
    async def test_delete_draft_api_error(self, mock_deps):
        """Test deleting a draft that does not exist."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Draft does not exist",
        }

        result = await delete_draft(99)

        assert result == {"status": "error", "error": "Draft does not exist"}
