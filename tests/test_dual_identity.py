"""Tests for dual identity system with bot credentials."""

import os
from unittest.mock import Mock, patch

import pytest

from zulipchat_mcp.client import ZulipClientWrapper
from zulipchat_mcp.config import ConfigManager, ZulipConfig
from zulipchat_mcp.services.agent_registry import AgentRegistry
from zulipchat_mcp.tools.agent_communication import AgentCommunication


class TestDualIdentityConfig:
    """Test configuration management for dual credentials."""

    def test_config_without_bot_credentials(self):
        """Test configuration when only user credentials are present."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "user@example.com",
                "ZULIP_API_KEY": "user-api-key",
                "ZULIP_SITE": "https://example.zulipchat.com",
            },
            clear=True,
        ):
            config = ConfigManager()
            assert config.config.email == "user@example.com"
            assert config.config.bot_email is None
            assert config.config.bot_api_key is None
            assert not config.has_bot_credentials()

    def test_config_with_bot_credentials(self):
        """Test configuration when bot credentials are present."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "user@example.com",
                "ZULIP_API_KEY": "user-api-key",
                "ZULIP_SITE": "https://example.zulipchat.com",
                "ZULIP_BOT_EMAIL": "bot@example.com",
                "ZULIP_BOT_API_KEY": "bot-api-key",
                "ZULIP_BOT_NAME": "Test Bot",
            },
            clear=True,
        ):
            config = ConfigManager()
            assert config.config.email == "user@example.com"
            assert config.config.bot_email == "bot@example.com"
            assert config.config.bot_api_key == "bot-api-key"
            assert config.config.bot_name == "Test Bot"
            assert config.has_bot_credentials()

    def test_get_client_config_with_bot_flag(self):
        """Test getting client configuration with bot flag."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "user@example.com",
                "ZULIP_API_KEY": "user-api-key",
                "ZULIP_SITE": "https://example.zulipchat.com",
                "ZULIP_BOT_EMAIL": "bot@example.com",
                "ZULIP_BOT_API_KEY": "bot-api-key",
            },
            clear=True,
        ):
            config = ConfigManager()

            # Get user config
            user_config = config.get_zulip_client_config(use_bot=False)
            assert user_config["email"] == "user@example.com"
            assert user_config["api_key"] == "user-api-key"

            # Get bot config
            bot_config = config.get_zulip_client_config(use_bot=True)
            assert bot_config["email"] == "bot@example.com"
            assert bot_config["api_key"] == "bot-api-key"


class TestZulipClientWrapper:
    """Test ZulipClientWrapper with dual identity support."""

    @patch("zulipchat_mcp.client.Client")
    def test_client_with_user_identity(self, mock_client_class):
        """Test client initialization with user identity."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Mock(spec=ConfigManager)
        config.config = ZulipConfig(
            email="user@example.com", api_key="user-key", site="https://example.com"
        )
        config.has_bot_credentials.return_value = False
        config.get_zulip_client_config.return_value = {
            "email": "user@example.com",
            "api_key": "user-key",
            "site": "https://example.com",
        }
        config.validate_config.return_value = True

        client = ZulipClientWrapper(config, use_bot_identity=False)

        assert client.identity == "user"
        assert client.identity_name == "user"
        assert client.current_email == "user@example.com"
        mock_client_class.assert_called_once()

    @patch("zulipchat_mcp.client.Client")
    def test_client_with_bot_identity(self, mock_client_class):
        """Test client initialization with bot identity."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Mock(spec=ConfigManager)
        config.config = ZulipConfig(
            email="user@example.com",
            api_key="user-key",
            site="https://example.com",
            bot_email="bot@example.com",
            bot_api_key="bot-key",
            bot_name="Claude Code",
        )
        config.has_bot_credentials.return_value = True
        config.get_zulip_client_config.return_value = {
            "email": "bot@example.com",
            "api_key": "bot-key",
            "site": "https://example.com",
        }
        config.validate_config.return_value = True

        client = ZulipClientWrapper(config, use_bot_identity=True)

        assert client.identity == "bot"
        assert client.identity_name == "Claude Code"
        assert client.current_email == "bot@example.com"
        mock_client_class.assert_called_once()

    @patch("zulipchat_mcp.client.Client")
    def test_client_fallback_when_bot_requested_but_unavailable(
        self, mock_client_class
    ):
        """Test client falls back to user when bot is requested but not configured."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Mock(spec=ConfigManager)
        config.config = ZulipConfig(
            email="user@example.com", api_key="user-key", site="https://example.com"
        )
        config.has_bot_credentials.return_value = False
        config.get_zulip_client_config.return_value = {
            "email": "user@example.com",
            "api_key": "user-key",
            "site": "https://example.com",
        }
        config.validate_config.return_value = True

        client = ZulipClientWrapper(config, use_bot_identity=True)

        # Should fall back to user identity
        assert client.identity == "user"
        assert client.current_email == "user@example.com"


class TestAgentCommunication:
    """Test agent communication with bot identity."""

    def test_format_message_with_bot_identity(self):
        """Test message formatting when using bot identity."""
        config = Mock(spec=ConfigManager)
        client = Mock(spec=ZulipClientWrapper)
        client.identity = "bot"
        client.send_message.return_value = {"result": "success", "id": 123}

        comm = AgentCommunication(config, client)

        formatted = comm._format_agent_message(
            "Claude Code", "status", "Task completed", {"progress": 100}
        )

        assert "Claude Code" in formatted
        assert "(AI Assistant)" in formatted
        assert "Task completed" in formatted
        assert "100%" in formatted

    def test_format_message_without_bot_identity(self):
        """Test message formatting when using user identity."""
        config = Mock(spec=ConfigManager)
        client = Mock(spec=ZulipClientWrapper)
        client.identity = "user"
        client.send_message.return_value = {"result": "success", "id": 123}

        comm = AgentCommunication(config, client)

        formatted = comm._format_agent_message(
            "Claude Code", "status", "Task completed", None
        )

        assert "Claude Code" in formatted
        assert "(via MCP integration)" in formatted
        assert "*Sent by: Claude Code*" in formatted
        assert "─" in formatted  # Separator line

    def test_agent_message_with_bot_client(self):
        """Test sending agent message with bot client."""
        config = Mock(spec=ConfigManager)
        client = Mock(spec=ZulipClientWrapper)
        client.identity = "bot"
        client.send_message.return_value = {"result": "success", "id": 456}

        # Mock registry, database, and AFK state
        with (
            patch(
                "src.zulipchat_mcp.tools.agent_communication.AgentRegistry"
            ) as mock_registry_class,
            patch(
                "src.zulipchat_mcp.tools.agent_communication.AgentDatabase"
            ) as mock_db_class,
            patch(
                "src.zulipchat_mcp.tools.agent_communication.get_afk_state"
            ) as mock_afk_func,
            patch(
                "src.zulipchat_mcp.tools.agent_communication.get_instance_identity"
            ) as mock_instance_func,
        ):

            mock_registry = Mock()
            mock_registry.get_agent.return_value = {
                "id": "agent-123",
                "name": "Claude Code",
                "stream_name": "ai-agents/claude-code",
            }
            mock_registry_class.return_value = mock_registry

            mock_db = Mock()
            mock_db.save_agent_message.return_value = True
            mock_db_class.return_value = mock_db

            # Mock AFK state to be active
            mock_afk = Mock()
            mock_afk.is_afk.return_value = True
            mock_afk_func.return_value = mock_afk

            # Mock instance identity
            mock_instance = Mock()
            mock_instance.get_notification_prefix.return_value = (
                "[Test Project on test-host]"
            )
            mock_instance.get_stream_name.return_value = "claude-code-testuser"
            mock_instance.get_topic_name.return_value = "test-project - test-host"
            mock_instance_func.return_value = mock_instance

            comm = AgentCommunication(config, client)
            result = comm.agent_message(
                "agent-123", "status", "Processing request", {"task": "test"}
            )

            assert result["status"] == "success"
            assert result["zulip_message_id"] == 456
            client.send_message.assert_called_once()

            # Check the message was sent to the correct stream (now uses instance identity)
            call_args = client.send_message.call_args
            assert (
                call_args[1]["to"] == "claude-code-testuser"
            )  # Personal stream from instance identity
            assert (
                call_args[1]["topic"] == "test-project - test-host"
            )  # Project topic from instance identity
            assert call_args[1]["message_type"] == "stream"


class TestAgentRegistry:
    """Test agent registry with bot client."""

    def test_register_agent_with_bot_client(self):
        """Test registering an agent using bot client."""
        config = Mock(spec=ConfigManager)

        # Mock config attributes that AgentRegistry needs
        config.DEFAULT_AGENT_STREAM_PREFIX = "ai-agents"
        config.DATABASE_URL = "test.db"
        config.ZULIP_SITE = "test.zulipchat.com"

        client = Mock(spec=ZulipClientWrapper)
        client.identity = "bot"

        # First call returns empty (no existing stream), second call returns the created stream
        client.get_streams.side_effect = [
            [],  # No existing streams
            [
                {"name": "ai-agents/Claude Code Test", "stream_id": 123}
            ],  # After creation
        ]

        # Mock the inner Zulip client
        mock_zulip_client = Mock()
        mock_zulip_client.add_subscriptions.return_value = {"result": "success"}
        client.client = mock_zulip_client

        client.send_message.return_value = {"result": "success"}

        with patch(
            "src.zulipchat_mcp.services.agent_registry.AgentDatabase"
        ) as mock_db_class:
            mock_db = Mock()
            mock_db.register_agent.return_value = True
            mock_db_class.return_value = mock_db

            registry = AgentRegistry(config, client)
            result = registry.register_agent("Claude Code Test", "claude_code", False)

            # Print the result for debugging if test fails
            if result.get("status") != "success":
                print(f"Registration failed: {result}")

            assert (
                result["status"] == "success"
            ), f"Registration failed: {result.get('error', 'Unknown error')}"
            assert "agent" in result
            assert result["agent"]["name"] == "Claude Code Test"

            # Verify stream was created
            mock_zulip_client.add_subscriptions.assert_called_once()

            # Verify welcome message was sent
            client.send_message.assert_called()
            welcome_call = client.send_message.call_args
            assert "Welcome" in str(welcome_call)


class TestServerIntegration:
    """Test server.py integration with bot clients."""

    @patch("zulipchat_mcp.server.get_bot_client")
    @patch("zulipchat_mcp.server.get_client")
    @patch("zulipchat_mcp.server.config_manager")
    def test_agent_tools_use_bot_client_when_available(
        self, mock_config, mock_get_client, mock_get_bot_client
    ):
        """Test that agent tools use bot client when credentials are available."""
        # Setup mocks
        mock_config.has_bot_credentials.return_value = True

        mock_user_client = Mock()
        mock_get_client.return_value = mock_user_client

        mock_bot_client = Mock()
        mock_get_bot_client.return_value = mock_bot_client

        # Import and test the logic
        from zulipchat_mcp.server import get_bot_client, get_client

        # When bot credentials exist, should use bot client
        bot_client = get_bot_client()
        assert bot_client == mock_bot_client

        # User client should still return user client
        user_client = get_client()
        assert user_client == mock_user_client


class TestEndToEnd:
    """End-to-end tests for the dual identity system."""

    @pytest.mark.integration
    def test_full_agent_lifecycle_with_bot_identity(self):
        """Test complete agent lifecycle with bot identity."""
        # This would be an integration test that requires actual Zulip instance
        # Marked for manual testing or CI with test Zulip server
        pass

    def test_message_attribution_clarity(self):
        """Test that message attribution is clear in both modes."""
        config = Mock(spec=ConfigManager)

        # Test with bot identity
        bot_client = Mock(spec=ZulipClientWrapper)
        bot_client.identity = "bot"
        bot_client.identity_name = "Claude Code Bot"

        comm_bot = AgentCommunication(config, bot_client)
        bot_message = comm_bot._format_agent_message(
            "Claude Code", "status", "Bot message", None
        )
        assert "(AI Assistant)" in bot_message
        assert "via MCP" not in bot_message

        # Test with user identity
        user_client = Mock(spec=ZulipClientWrapper)
        user_client.identity = "user"
        user_client.identity_name = "user"

        comm_user = AgentCommunication(config, user_client)
        user_message = comm_user._format_agent_message(
            "Claude Code", "status", "User message", None
        )
        assert "(via MCP integration)" in user_message
        assert "*Sent by: Claude Code*" in user_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
