"""Tests for tools/messaging.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.messaging import (
    cross_post_message,
    edit_message,
    get_message,
    sanitize_content,
    send_message,
)


class TestMessagingTools:
    """Tests for messaging tools."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper instance."""
        client = MagicMock()
        client.send_message.return_value = {"result": "success", "id": 100}
        client.edit_message.return_value = {"result": "success"}
        client.get_message.return_value = {
            "result": "success",
            "message": {
                "content": "original",
                "subject": "topic",
                "display_recipient": "stream",
            },
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch ConfigManager and ZulipClientWrapper."""
        with (
            patch("src.zulipchat_mcp.tools.messaging.ConfigManager") as mock_config_cls,
            patch(
                "src.zulipchat_mcp.tools.messaging.ZulipClientWrapper"
            ) as mock_client_cls,
        ):
            mock_client_cls.return_value = mock_client
            yield mock_client

    def test_sanitize_content(self):
        """Test content sanitization."""
        short = "short"
        assert sanitize_content(short) == short

        long_content = "a" * 50005
        sanitized = sanitize_content(long_content, max_length=50000)
        assert len(sanitized) > 50000
        assert sanitized.endswith("... [Content truncated]")

    @pytest.mark.asyncio
    async def test_send_message_stream(self, mock_deps):
        """Test sending stream message."""
        result = await send_message("stream", "general", "hello", "topic")
        assert result["status"] == "success"
        assert result["message_id"] == 100

        mock_deps.send_message.assert_called_with("stream", "general", "hello", "topic")

    @pytest.mark.asyncio
    async def test_send_message_private(self, mock_deps):
        """Test sending private message."""
        result = await send_message("private", "user@example.com", "hello")
        assert result["status"] == "success"

        mock_deps.send_message.assert_called_with(
            "private", "user@example.com", "hello", None
        )

    @pytest.mark.asyncio
    async def test_send_message_invalid(self, mock_deps):
        """Test invalid send message params."""
        # Missing topic for stream
        result = await send_message("stream", "general", "hello")
        assert result["status"] == "error"
        assert "Topic required" in result["error"]

        # Empty recipient
        result = await send_message("private", [], "hello")
        assert result["status"] == "error"
        assert "Recipient list cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_edit_message(self, mock_deps):
        """Test edit message."""
        result = await edit_message(1, content="new")
        assert result["status"] == "success"
        assert "content" in result["changes"]

        mock_deps.edit_message.assert_called()
        args = mock_deps.edit_message.call_args[1]
        assert args["message_id"] == 1
        assert args["content"] == "new"

    @pytest.mark.asyncio
    async def test_edit_message_invalid(self, mock_deps):
        """Test edit message invalid params."""
        # Invalid ID
        result = await edit_message(0, content="new")
        assert result["status"] == "error"

        # Nothing to edit
        result = await edit_message(1)
        assert result["status"] == "error"
        assert "Must provide content" in result["error"]

        # Invalid propagate mode
        result = await edit_message(1, content="new", propagate_mode="invalid")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_message(self, mock_deps):
        """Test get message."""
        result = await get_message(1)
        assert result["status"] == "success"
        assert result["message"]["content"] == "original"

        # Not found
        mock_deps.get_message.return_value = {"result": "error", "msg": "Not found"}
        result = await get_message(2)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_cross_post_message(self, mock_deps):
        """Test cross post message."""
        # get_message already mocked in fixture to return "original"

        result = await cross_post_message(1, ["stream2"])

        assert result["status"] == "success"
        assert len(result["results"]) == 1
        assert result["results"][0]["stream"] == "stream2"

        # Verify call to send_message logic (which calls client.send_message)
        # cross_post_message calls send_message internal function, which creates NEW client instance.
        # But we patched ZulipClientWrapper globally in the module.
        # So send_message will use the same mock_client_cls which returns mock_client.

        # Check send_message calls
        # 1st call was get_message (implied)
        # 2nd call is send_message
        assert mock_deps.send_message.call_count == 1
        args = mock_deps.send_message.call_args
        # args[0] are positional: (type, to, content, topic)
        assert args[0][0] == "stream"
        assert args[0][1] == "stream2"
        assert "Cross-posted" in args[0][2]  # Default prefix
        assert args[0][3] == "topic"  # From original message

    @pytest.mark.asyncio
    async def test_cross_post_message_custom_prefix(self, mock_deps):
        """Test cross post with custom prefix."""
        await cross_post_message(1, ["stream2"], custom_prefix="PREFIX: ")

        args = mock_deps.send_message.call_args
        assert args[0][2].startswith("PREFIX: original")

    @pytest.mark.asyncio
    async def test_cross_post_message_source_failed(self, mock_deps):
        """Test cross post when source message not found."""
        mock_deps.get_message.return_value = {"result": "error"}

        result = await cross_post_message(1, ["stream2"])
        assert result["status"] == "error"
        assert "Source message not found" in result["error"]
