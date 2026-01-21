"""Tests for tools/system.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.system import (
    register_system_tools,
    server_info,
    switch_identity,
)


class TestSystemTools:
    """Tests for system tools."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper instance."""
        client = MagicMock()
        client.identity = "user"
        client.identity_name = "Test User"
        client.current_email = "test@example.com"
        return client

    @pytest.fixture
    def mock_config(self):
        """Mock ConfigManager instance."""
        config = MagicMock()
        config.has_bot_credentials.return_value = True
        config.config.email = "test@example.com"
        config.config.bot_email = "bot@example.com"
        config.config.bot_name = "Test Bot"
        config.config.site = "https://test.zulipchat.com"
        return config

    @pytest.fixture
    def mock_deps(self, mock_client, mock_config):
        """Patch ConfigManager and ZulipClientWrapper."""
        with (
            patch(
                "src.zulipchat_mcp.tools.system.ConfigManager"
            ) as mock_config_cls,
            patch(
                "src.zulipchat_mcp.tools.system.ZulipClientWrapper"
            ) as mock_client_cls,
        ):
            mock_config_cls.return_value = mock_config
            mock_client_cls.return_value = mock_client
            yield {"config": mock_config, "client": mock_client}


class TestSwitchIdentity(TestSystemTools):
    """Tests for switch_identity function."""

    @pytest.mark.asyncio
    async def test_switch_to_user_identity(self, mock_deps):
        """Test switching to user identity."""
        result = await switch_identity("user")

        assert result["status"] == "success"
        assert result["identity"] == "user"
        assert result["identity_name"] == "Test User"
        assert result["current_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_switch_to_bot_identity(self, mock_deps):
        """Test switching to bot identity."""
        mock_deps["client"].identity = "bot"
        mock_deps["client"].identity_name = "Test Bot"
        mock_deps["client"].current_email = "bot@example.com"

        result = await switch_identity("bot")

        assert result["status"] == "success"
        assert result["identity"] == "bot"
        assert result["identity_name"] == "Test Bot"
        assert result["current_email"] == "bot@example.com"

    @pytest.mark.asyncio
    async def test_switch_to_bot_without_credentials(self, mock_deps):
        """Test switching to bot when credentials not configured."""
        mock_deps["config"].has_bot_credentials.return_value = False

        result = await switch_identity("bot")

        assert result["status"] == "error"
        assert "Bot credentials not configured" in result["error"]
        assert "suggestion" in result
        assert "ZULIP_BOT_EMAIL" in result["suggestion"]

    @pytest.mark.asyncio
    async def test_switch_identity_exception(self, mock_deps):
        """Test switch_identity handles exceptions."""
        with patch(
            "src.zulipchat_mcp.tools.system.ZulipClientWrapper"
        ) as mock_client_cls:
            mock_client_cls.side_effect = Exception("Connection failed")

            result = await switch_identity("user")

            assert result["status"] == "error"
            assert "Connection failed" in result["error"]


class TestServerInfo(TestSystemTools):
    """Tests for server_info function."""

    @pytest.mark.asyncio
    async def test_server_info_with_bot_credentials(self, mock_deps):
        """Test server_info returns complete information with bot configured."""
        result = await server_info()

        assert result["status"] == "success"
        assert result["server_name"] == "ZulipChat MCP"
        assert result["version"] == "0.4.0"
        assert result["zulip_site"] == "https://test.zulipchat.com"

        # Check user identity info
        assert result["available_identities"]["user"]["available"] is True
        assert result["available_identities"]["user"]["email"] == "test@example.com"

        # Check bot identity info
        assert result["available_identities"]["bot"]["available"] is True
        assert result["available_identities"]["bot"]["email"] == "bot@example.com"
        assert result["available_identities"]["bot"]["name"] == "Test Bot"

        # Check features list
        assert "messaging" in result["features"]
        assert "dual_identity" in result["features"]
        assert "search_with_fuzzy_users" in result["features"]

    @pytest.mark.asyncio
    async def test_server_info_without_bot_credentials(self, mock_deps):
        """Test server_info when bot credentials not configured."""
        mock_deps["config"].has_bot_credentials.return_value = False
        mock_deps["config"].config.bot_email = None
        mock_deps["config"].config.bot_name = None

        result = await server_info()

        assert result["status"] == "success"
        assert result["available_identities"]["user"]["available"] is True
        assert result["available_identities"]["bot"]["available"] is False
        assert result["available_identities"]["bot"]["email"] is None

    @pytest.mark.asyncio
    async def test_server_info_features_list(self, mock_deps):
        """Test server_info returns expected features."""
        result = await server_info()

        expected_features = [
            "messaging",
            "search_with_fuzzy_users",
            "stream_management",
            "user_management",
            "event_system",
            "file_uploads",
            "dual_identity",
        ]

        assert result["features"] == expected_features


class TestRegisterSystemTools:
    """Tests for register_system_tools function."""

    def test_register_system_tools(self):
        """Test that system tools are registered with MCP."""
        mock_mcp = MagicMock()

        register_system_tools(mock_mcp)

        # Verify tool() was called twice (for switch_identity and server_info)
        assert mock_mcp.tool.call_count == 2

        # Check the calls
        calls = mock_mcp.tool.call_args_list

        # First call: switch_identity
        assert calls[0].kwargs["name"] == "switch_identity"
        assert "identities" in calls[0].kwargs["description"].lower()

        # Second call: server_info
        assert calls[1].kwargs["name"] == "server_info"
        assert "server" in calls[1].kwargs["description"].lower()

    def test_register_system_tools_correct_functions(self):
        """Test that correct functions are registered."""
        mock_mcp = MagicMock()
        # Setup chained call to track what function is registered
        mock_tool_decorator = MagicMock()
        mock_mcp.tool.return_value = mock_tool_decorator

        register_system_tools(mock_mcp)

        # Verify both decorators were called with the actual functions
        decorator_calls = mock_tool_decorator.call_args_list
        assert len(decorator_calls) == 2

        # The first call should be with switch_identity function
        assert decorator_calls[0].args[0] == switch_identity

        # The second call should be with server_info function
        assert decorator_calls[1].args[0] == server_info
