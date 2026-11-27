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
        """Patch get_client to return mock client."""
        with patch("src.zulipchat_mcp.tools.messaging.get_client") as mock_get_client:
            mock_get_client.return_value = mock_client
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
            "private", ["user@example.com"], "hello", None
        )

    @pytest.mark.asyncio
    async def test_identical_repeat_is_suppressed_and_reports_original(self, mock_deps):
        mock_deps.current_email = "user@example.com"
        mock_deps.identity = "user"
        first = await send_message("private", ["b@x.com", "A@x.com"], "hi")
        repeat = await send_message("private", ["a@x.com", "b@x.com"], "hi")
        assert mock_deps.send_message.call_count == 1
        assert repeat["duplicate_suppressed"] is True
        assert repeat["message_id"] == first["message_id"] == 100
        assert first["sent_as"] == "user"

        await send_message(
            "private", ["a@x.com", "b@x.com"], "hi", allow_duplicate=True
        )
        await send_message("private", ["a@x.com", "b@x.com"], "different")
        assert mock_deps.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_failed_send_is_not_remembered(self, mock_deps):
        mock_deps.send_message.return_value = {"result": "error", "msg": "nope"}
        await send_message("stream", "general", "hello", "topic")
        mock_deps.send_message.return_value = {"result": "success", "id": 7}
        result = await send_message("stream", "general", "hello", "topic")
        assert result["message_id"] == 7 and "duplicate_suppressed" not in result

    @pytest.mark.asyncio
    async def test_as_bot_uses_bot_client_for_one_send(self, mock_deps):
        bot = MagicMock(identity="bot", current_email="bot@x.com")
        bot.send_message.return_value = {"result": "success", "id": 9}
        config = MagicMock()
        config.has_bot_credentials.return_value = True
        with (
            patch("src.zulipchat_mcp.tools.messaging.get_bot_client", return_value=bot),
            patch(
                "src.zulipchat_mcp.tools.messaging.get_config_manager",
                return_value=config,
            ),
        ):
            result = await send_message("private", "jaime@x.com", "hi", as_bot=True)
        assert result["sent_as"] == "bot"
        mock_deps.send_message.assert_not_called()

        config.has_bot_credentials.return_value = False
        with patch(
            "src.zulipchat_mcp.tools.messaging.get_config_manager", return_value=config
        ):
            missing = await send_message("private", "jaime@x.com", "hi", as_bot=True)
        assert missing["status"] == "error" and missing["error"]["retryable"] is False

    @pytest.mark.asyncio
    async def test_send_message_invalid(self, mock_deps):
        """Test invalid send message params."""
        # Missing topic for stream
        result = await send_message("stream", "general", "hello")
        assert result["status"] == "error"
        assert "Topic required" in result["error"]["message"]

        # Empty recipient
        result = await send_message("private", [], "hello")
        assert result["status"] == "error"
        assert "Recipient list cannot be empty" in result["error"]["message"]

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
        assert "Must provide content" in result["error"]["message"]

        # Invalid propagate mode
        result = await edit_message(1, content="new", propagate_mode="invalid")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_message(self, mock_deps):
        """Test get message."""
        result = await get_message(1)
        assert result["status"] == "success"
        assert result["message"]["content"] == "original"
        assert result["content_format"] == "rendered_html"
        mock_deps.get_message.assert_called_with(1)

        result = await get_message(1, content_format="markdown")
        assert result["content_format"] == "markdown"
        mock_deps.get_message.assert_called_with(1, apply_markdown=False)

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
        assert "Source message not found" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_message_truncates_long_content(self, mock_deps):
        mock_deps.get_message.return_value = {
            "result": "success",
            "message": {"id": 1, "content": "x" * 50},
        }
        result = await get_message(1, max_chars=10)
        assert result["message"]["content"] == "x" * 10
        assert result["content_truncated"] is True
        assert result["content_chars"] == 50
        short = await get_message(1, max_chars=50)
        assert "content_truncated" not in short


class TestRecipientResolution:
    """Direct messages by name resolve to exactly one person or send nothing."""

    ROSTER = {
        "result": "success",
        "members": [
            {"user_id": 7, "full_name": "Jaime Cernuda", "email": "j@x.com"},
            {"user_id": 8, "full_name": "Jamie Lee", "email": "jl@x.com"},
            {"user_id": 9, "full_name": "Anthony Kougkas", "email": "a@x.com"},
            {"user_id": 10, "full_name": "Anna Smith", "email": "an@x.com"},
            {"user_id": 11, "full_name": "Old Hand", "is_active": False},
        ],
    }

    @pytest.fixture
    def client(self):
        client = MagicMock()
        client.get_users.return_value = self.ROSTER
        client.send_message.return_value = {
            "result": "success",
            "id": 5,
            "message_link": "https://x/#narrow/near/5",
        }
        with patch("src.zulipchat_mcp.tools.messaging.get_client", return_value=client):
            yield client

    @pytest.mark.asyncio
    async def test_first_name_resolves_to_user_id_and_returns_link(self, client):
        result = await send_message("direct", "jaime", "PR is ready")
        client.send_message.assert_called_once_with("private", [7], "PR is ready", None)
        assert result["message_link"] == "https://x/#narrow/near/5"

    @pytest.mark.asyncio
    async def test_near_miss_name_sends_nothing(self, client):
        result = await send_message("direct", "Jaimie", "hi")
        client.send_message.assert_not_called()
        assert result["error"]["code"] == "UNKNOWN_RECIPIENT"
        assert result["error"]["retryable"] is False

    @pytest.mark.asyncio
    async def test_ambiguous_prefix_returns_candidates(self, client):
        result = await send_message("direct", "an", "hi")
        client.send_message.assert_not_called()
        assert result["error"]["code"] == "AMBIGUOUS_RECIPIENT"
        assert {c["user_id"] for c in result["candidates"]} == {9, 10}

    @pytest.mark.asyncio
    async def test_emails_and_ids_skip_the_roster(self, client):
        await send_message("direct", ["a@x.com", "12", 13], "hi")
        client.get_users.assert_not_called()
        client.send_message.assert_called_once_with(
            "private", ["a@x.com", 12, 13], "hi", None
        )

    @pytest.mark.asyncio
    async def test_inactive_users_never_match(self, client):
        result = await send_message("direct", "Old Hand", "hi")
        assert result["error"]["code"] == "UNKNOWN_RECIPIENT"

    @pytest.mark.asyncio
    async def test_channel_shorthand_strips_hash(self, client):
        await send_message("channel", "#dev", "hi", "build")
        client.send_message.assert_called_once_with("stream", "dev", "hi", "build")
