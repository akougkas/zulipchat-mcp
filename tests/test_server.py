"""Tests for ZulipChat MCP server."""

import os
from unittest.mock import Mock, patch

import pytest

from src.zulipchat_mcp.client import (
    ZulipClientWrapper,
    ZulipMessage,
    ZulipStream,
    ZulipUser,
)
from src.zulipchat_mcp.config import ConfigManager


class TestConfigManager:
    """Test configuration management."""

    def test_config_from_env_vars(self):
        """Test configuration loading from environment variables."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "test@example.com",
                "ZULIP_API_KEY": "test-key",
                "ZULIP_SITE": "https://test.zulipchat.com",
            },
        ):
            config_manager = ConfigManager()
            assert config_manager.config.email == "test@example.com"
            assert config_manager.config.api_key == "test-key"
            assert config_manager.config.site == "https://test.zulipchat.com"

    def test_config_validation_valid(self):
        """Test validation with valid configuration."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "test@example.com",
                "ZULIP_API_KEY": "test-key-1234567890",
                "ZULIP_SITE": "https://test.zulipchat.com",
            },
        ):
            config_manager = ConfigManager()
            assert config_manager.validate_config() is True

    def test_config_validation_invalid_email(self):
        """Test validation with invalid email."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "invalid-email",
                "ZULIP_API_KEY": "test-key-1234567890",
                "ZULIP_SITE": "https://test.zulipchat.com",
            },
        ):
            config_manager = ConfigManager()
            assert config_manager.validate_config() is False

    def test_config_validation_invalid_api_key(self):
        """Test validation with invalid API key."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "test@example.com",
                "ZULIP_API_KEY": "short",
                "ZULIP_SITE": "https://test.zulipchat.com",
            },
        ):
            config_manager = ConfigManager()
            assert config_manager.validate_config() is False

    def test_config_validation_invalid_site(self):
        """Test validation with invalid site URL."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "test@example.com",
                "ZULIP_API_KEY": "test-key-1234567890",
                "ZULIP_SITE": "invalid-url",
            },
        ):
            config_manager = ConfigManager()
            assert config_manager.validate_config() is False

    def test_zulip_client_config(self):
        """Test Zulip client configuration generation."""
        with patch.dict(
            os.environ,
            {
                "ZULIP_EMAIL": "test@example.com",
                "ZULIP_API_KEY": "test-key",
                "ZULIP_SITE": "https://test.zulipchat.com",
            },
        ):
            config_manager = ConfigManager()
            client_config = config_manager.get_zulip_client_config()

            assert client_config["email"] == "test@example.com"
            assert client_config["api_key"] == "test-key"
            assert client_config["site"] == "https://test.zulipchat.com"


class TestZulipClientWrapper:
    """Test Zulip client wrapper."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        config_manager = Mock()
        config_manager.validate_config.return_value = True
        config_manager.get_zulip_client_config.return_value = {
            "email": "test@example.com",
            "api_key": "test-key",
            "site": "https://test.zulipchat.com",
        }
        return config_manager

    @pytest.fixture
    def mock_zulip_client(self):
        """Create mock Zulip client."""
        client = Mock()
        return client

    def test_client_initialization(self, mock_config_manager):
        """Test client initialization."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)

            assert wrapper.config_manager == mock_config_manager
            assert wrapper.client == mock_client
            mock_config_manager.validate_config.assert_called_once()
            mock_config_manager.get_zulip_client_config.assert_called_once()

    def test_send_message_stream(self, mock_config_manager):
        """Test sending message to stream."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.send_message.return_value = {"result": "success", "id": 123}
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)
            result = wrapper.send_message(
                "stream", "test-stream", "Hello world", "test-topic"
            )

            expected_request = {
                "type": "stream",
                "to": "test-stream",
                "content": "Hello world",
                "topic": "test-topic",
            }
            mock_client.send_message.assert_called_once_with(expected_request)
            assert result == {"result": "success", "id": 123}

    def test_send_message_private(self, mock_config_manager):
        """Test sending private message."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.send_message.return_value = {"result": "success", "id": 456}
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)
            result = wrapper.send_message("private", "user@example.com", "Hello!")

            expected_request = {
                "type": "private",
                "to": ["user@example.com"],
                "content": "Hello!",
            }
            mock_client.send_message.assert_called_once_with(expected_request)
            assert result == {"result": "success", "id": 456}

    def test_get_messages(self, mock_config_manager):
        """Test getting messages."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = {
                "result": "success",
                "messages": [
                    {
                        "id": 1,
                        "sender_full_name": "John Doe",
                        "sender_email": "john@example.com",
                        "timestamp": 1640995200,
                        "content": "Hello world!",
                        "display_recipient": "general",
                        "subject": "test topic",
                        "type": "stream",
                        "reactions": [],
                    }
                ],
            }
            mock_client.get_messages.return_value = mock_response
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)
            messages = wrapper.get_messages()

            assert len(messages) == 1
            msg = messages[0]
            assert isinstance(msg, ZulipMessage)
            assert msg.id == 1
            assert msg.sender_full_name == "John Doe"
            assert msg.content == "Hello world!"

    def test_get_streams(self, mock_config_manager):
        """Test getting streams."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = {
                "result": "success",
                "streams": [
                    {
                        "stream_id": 1,
                        "name": "general",
                        "description": "General discussion",
                        "invite_only": False,
                    }
                ],
            }
            mock_client.get_streams.return_value = mock_response
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)
            streams = wrapper.get_streams()

            assert len(streams) == 1
            stream = streams[0]
            assert isinstance(stream, ZulipStream)
            assert stream.stream_id == 1
            assert stream.name == "general"
            assert stream.is_private is False

    def test_get_users(self, mock_config_manager):
        """Test getting users."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = {
                "result": "success",
                "members": [
                    {
                        "user_id": 1,
                        "full_name": "John Doe",
                        "email": "john@example.com",
                        "is_active": True,
                        "is_bot": False,
                        "avatar_url": "https://example.com/avatar.jpg",
                    }
                ],
            }
            mock_client.get_users.return_value = mock_response
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)
            users = wrapper.get_users()

            assert len(users) == 1
            user = users[0]
            assert isinstance(user, ZulipUser)
            assert user.user_id == 1
            assert user.full_name == "John Doe"
            assert user.is_bot is False

    def test_add_reaction(self, mock_config_manager):
        """Test adding reaction to message."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.add_reaction.return_value = {"result": "success"}
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)
            result = wrapper.add_reaction(123, "thumbs_up")

            expected_request = {"message_id": 123, "emoji_name": "thumbs_up"}
            mock_client.add_reaction.assert_called_once_with(expected_request)
            assert result == {"result": "success"}

    def test_edit_message(self, mock_config_manager):
        """Test editing message."""
        with patch("src.zulipchat_mcp.client.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.update_message.return_value = {"result": "success"}
            mock_client_class.return_value = mock_client

            wrapper = ZulipClientWrapper(mock_config_manager)
            result = wrapper.edit_message(
                123, content="Updated content", topic="New topic"
            )

            expected_request = {
                "message_id": 123,
                "content": "Updated content",
                "topic": "New topic",
            }
            mock_client.update_message.assert_called_once_with(expected_request)
            assert result == {"result": "success"}


class TestDataModels:
    """Test Pydantic data models."""

    def test_zulip_message_model(self):
        """Test ZulipMessage model."""
        message_data = {
            "id": 123,
            "sender_full_name": "John Doe",
            "sender_email": "john@example.com",
            "timestamp": 1640995200,
            "content": "Hello world!",
            "stream_name": "general",
            "subject": "test topic",
            "type": "stream",
            "reactions": [],
        }

        message = ZulipMessage(**message_data)
        assert message.id == 123
        assert message.sender_full_name == "John Doe"
        assert message.content == "Hello world!"

    def test_zulip_stream_model(self):
        """Test ZulipStream model."""
        stream_data = {
            "stream_id": 1,
            "name": "general",
            "description": "General discussion",
            "is_private": False,
        }

        stream = ZulipStream(**stream_data)
        assert stream.stream_id == 1
        assert stream.name == "general"
        assert stream.is_private is False

    def test_zulip_user_model(self):
        """Test ZulipUser model."""
        user_data = {
            "user_id": 1,
            "full_name": "John Doe",
            "email": "john@example.com",
            "is_active": True,
            "is_bot": False,
            "avatar_url": "https://example.com/avatar.jpg",
        }

        user = ZulipUser(**user_data)
        assert user.user_id == 1
        assert user.full_name == "John Doe"
        assert user.is_bot is False


class TestMCPServer:
    """Test MCP server functionality."""

    def test_server_import(self):
        """Test that server module can be imported."""
        try:
            from src.zulipchat_mcp import server

            assert hasattr(server, "main")
            assert hasattr(server, "mcp")
        except ImportError as e:
            pytest.fail(f"Failed to import server module: {e}")

    @patch("src.zulipchat_mcp.server.get_client")
    def test_send_message_tool(self, mock_get_client):
        """Test send_message MCP tool."""
        from src.zulipchat_mcp.server import send_message

        mock_client = Mock()
        mock_client.send_message.return_value = {"result": "success", "id": 123}
        mock_get_client.return_value = mock_client

        result = send_message("stream", "general", "Hello world!", "test-topic")

        mock_client.send_message.assert_called_once_with(
            "stream", "general", "Hello world!", "test-topic"
        )
        assert result == {"result": "success", "id": 123}

    @patch("src.zulipchat_mcp.server.get_client")
    def test_get_messages_tool(self, mock_get_client):
        """Test get_messages MCP tool."""
        from src.zulipchat_mcp.server import get_messages

        mock_message = ZulipMessage(
            id=1,
            sender_full_name="John Doe",
            sender_email="john@example.com",
            timestamp=1640995200,
            content="Hello!",
            type="stream",
        )

        mock_client = Mock()
        mock_client.get_messages_from_stream.return_value = [mock_message]
        mock_get_client.return_value = mock_client

        result = get_messages(stream_name="general")

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["sender"] == "John Doe"
        assert result[0]["content"] == "Hello!"


if __name__ == "__main__":
    pytest.main([__file__])
