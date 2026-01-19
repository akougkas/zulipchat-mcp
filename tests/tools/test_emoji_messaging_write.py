"""Tests for write operations in tools/emoji_messaging.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.emoji_messaging import add_reaction, remove_reaction


class TestReactions:
    """Tests for add/remove reaction functions."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.add_reaction.return_value = {"result": "success"}
        client.remove_reaction.return_value = {"result": "success"}
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.emoji_messaging.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.emoji_messaging.ZulipClientWrapper"
            ) as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_add_valid_reaction(self, mock_deps):
        """Test adding a valid unicode reaction."""
        result = await add_reaction(100, "thumbs_up")
        assert result["status"] == "success"
        assert result["reaction_type"] == "unicode_emoji"
        mock_deps.add_reaction.assert_called_with(100, "thumbs_up")

    @pytest.mark.asyncio
    async def test_add_custom_emoji(self, mock_deps):
        """Test adding a custom emoji (realm_emoji)."""
        # We use a valid emoji name from the registry, even if we say it's realm_emoji
        result = await add_reaction(100, "thumbs_up", reaction_type="realm_emoji")
        assert result["status"] == "success"
        assert result["reaction_type"] == "realm_emoji"
        # Note: The current implementation passes positional args to client.add_reaction(id, name)
        # It seemingly ignores reaction_type/code in the call to client!
        # But we test what the TOOL returns and what it calls on the client.
        mock_deps.add_reaction.assert_called_with(100, "thumbs_up")

    @pytest.mark.asyncio
    async def test_add_to_nonexistent_message(self, mock_deps):
        """Test adding reaction to nonexistent message."""
        mock_deps.add_reaction.return_value = {
            "result": "error",
            "msg": "Invalid message(s)",
        }
        result = await add_reaction(999, "thumbs_up")
        assert result["status"] == "error"
        assert "Invalid message" in result["error"]

    @pytest.mark.asyncio
    async def test_add_invalid_emoji(self, mock_deps):
        """Test adding reaction with invalid emoji name (injection check)."""
        # Name with special chars
        result = await add_reaction(100, "smile; DROP TABLE")
        assert result["status"] == "error"
        assert "not approved" in result["error"]["message"]

        # Empty name
        result = await add_reaction(100, "")
        assert result["status"] == "error"

        # Too long
        result = await add_reaction(100, "a" * 51)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_add_duplicate_reaction(self, mock_deps):
        """Test adding a reaction that already exists."""
        mock_deps.add_reaction.return_value = {
            "result": "error",
            "msg": "Reaction already exists",
        }
        result = await add_reaction(100, "thumbs_up")
        assert result["status"] == "error"
        assert "Reaction already exists" in result["error"]

    @pytest.mark.asyncio
    async def test_remove_own_reaction(self, mock_deps):
        """Test removing own reaction."""
        result = await remove_reaction(100, "smile")
        assert result["status"] == "success"
        assert result["action"] == "removed"
        mock_deps.remove_reaction.assert_called_with(100, "smile")

    @pytest.mark.asyncio
    async def test_remove_others_reaction_fails(self, mock_deps):
        """Test removing others' reaction (mocking backend rejection, if API supported it).
        Zulip API typically only allows removing own reactions unless admin?
        We assume client.remove_reaction handles the API call and returns error if forbidden.
        """
        mock_deps.remove_reaction.return_value = {
            "result": "error",
            "msg": "Not authorized",
        }
        result = await remove_reaction(100, "smile")
        assert result["status"] == "error"
        assert "Not authorized" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_message_id(self, mock_deps):
        """Test invalid message ID validation."""
        result = await add_reaction(0, "smile")
        assert result["status"] == "error"
        assert "Invalid message ID" in result["error"]["message"]

        result = await remove_reaction(-1, "smile")
        assert result["status"] == "error"
