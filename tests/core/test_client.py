"""Tests for core/client.py."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.config import ConfigManager, ZulipConfig
from src.zulipchat_mcp.core.client import ZulipClientWrapper, ZulipMessage


class TestZulipClientWrapper:
    """Tests for ZulipClientWrapper."""

    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager."""
        config_data = ZulipConfig(
            email="test@example.com",
            api_key="key",
            site="https://chat.zulip.org",
            bot_email="bot@example.com",
            bot_api_key="botkey",
            bot_name="Bot",
        )
        manager = MagicMock(spec=ConfigManager)
        manager.config = config_data
        manager.validate_config.return_value = True
        manager.has_bot_credentials.return_value = True

        manager.get_zulip_client_config.side_effect = lambda use_bot: {
            "email": "bot@example.com" if use_bot else "test@example.com",
            "api_key": "botkey" if use_bot else "key",
            "site": "https://chat.zulip.org",
            "config_file": None,
        }
        return manager

    @pytest.fixture
    def mock_zulip_client(self):
        """Mock underlying zulip.Client."""
        with patch("src.zulipchat_mcp.core.client.Client") as mock:
            client_instance = MagicMock()
            mock.return_value = client_instance
            yield client_instance

    def test_init_validation_failure(self):
        """Test initialization fails if config invalid."""
        manager = MagicMock(spec=ConfigManager)
        manager.validate_config.return_value = False

        with pytest.raises(ValueError, match="Invalid Zulip configuration"):
            ZulipClientWrapper(config_manager=manager)

    def test_init_user_identity(self, mock_config_manager, mock_zulip_client):
        """Test initialization with user identity."""
        wrapper = ZulipClientWrapper(
            config_manager=mock_config_manager, use_bot_identity=False
        )
        assert wrapper.identity == "user"
        assert wrapper.identity_name == "test"  # from email split
        assert wrapper.current_email == "test@example.com"

    def test_init_bot_identity(self, mock_config_manager, mock_zulip_client):
        """Test initialization with bot identity."""
        wrapper = ZulipClientWrapper(
            config_manager=mock_config_manager, use_bot_identity=True
        )
        assert wrapper.identity == "bot"
        assert wrapper.identity_name == "Bot"
        assert wrapper.current_email == "bot@example.com"

    def test_base_url_normalized_from_config_file_client(self, mock_zulip_client):
        """Test config-file client base_url strips API suffixes."""
        manager = MagicMock(spec=ConfigManager)
        manager.validate_config.return_value = True
        manager.has_bot_credentials.return_value = False
        manager.get_zulip_client_config.return_value = {
            "email": None,
            "api_key": None,
            "site": None,
            "config_file": "/tmp/zuliprc",
        }

        mock_zulip_client.base_url = "https://ai4hpc.zulipchat.com/api/v1"
        mock_zulip_client.email = "test@example.com"

        wrapper = ZulipClientWrapper(config_manager=manager)

        assert wrapper.base_url == "https://ai4hpc.zulipchat.com"

    def test_lazy_loading(self, mock_config_manager, mock_zulip_client):
        """Test client is created only when accessed."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)
        assert wrapper._client is None

        # Access client property
        _ = wrapper.client
        assert wrapper._client is not None

        # Verify Client constructor called with correct args
        from src.zulipchat_mcp.core.client import Client

        Client.assert_called_with(
            email="test@example.com",
            api_key="key",
            site="https://chat.zulip.org",
            retry_on_errors=False,
            client="zulipchat-mcp",
        )

    def test_send_message_stream(self, mock_config_manager, mock_zulip_client):
        """Current servers receive the channel wire type."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)
        mock_zulip_client.feature_level = 513
        mock_zulip_client.send_message.return_value = {
            "result": "success",
            "id": 1,
            "message_link": "https://z/#narrow/near/1",
        }

        result = wrapper.send_message("stream", "general", "hello", "topic1")

        mock_zulip_client.send_message.assert_called_with(
            {"type": "channel", "to": "general", "topic": "topic1", "content": "hello"}
        )
        assert result["message_link"] == "https://z/#narrow/near/1"

    def test_send_message_private(self, mock_config_manager, mock_zulip_client):
        """Current servers receive the direct wire type."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)
        mock_zulip_client.feature_level = 513
        mock_zulip_client.send_message.return_value = {"result": "success", "id": 1}

        wrapper.send_message("private", "user@example.com", "hello")

        mock_zulip_client.send_message.assert_called_with(
            {"type": "direct", "to": ["user@example.com"], "content": "hello"}
        )

    @pytest.mark.parametrize(
        ("level", "channel", "direct"),
        [
            (100, "stream", "private"),
            (200, "stream", "direct"),
            (0, "channel", "direct"),
        ],
    )
    def test_send_message_wire_type_by_feature_level(
        self, mock_config_manager, mock_zulip_client, level, channel, direct
    ):
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)
        mock_zulip_client.feature_level = level
        mock_zulip_client.send_message.return_value = {"result": "success"}

        wrapper.send_message("channel", 7, "hi", "t")
        assert mock_zulip_client.send_message.call_args[0][0]["type"] == channel
        assert mock_zulip_client.send_message.call_args[0][0]["to"] == 7
        wrapper.send_message("direct", [1, 2], "hi")
        assert mock_zulip_client.send_message.call_args[0][0] == {
            "type": direct,
            "to": [1, 2],
            "content": "hi",
        }

    def test_send_message_rejects_unknown_type(
        self, mock_config_manager, mock_zulip_client
    ):
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)
        with pytest.raises(ValueError):
            wrapper.send_message("broadcast", "general", "hi")

    def test_get_messages_raw(self, mock_config_manager, mock_zulip_client):
        """Test getting raw messages."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)
        mock_zulip_client.get_messages.return_value = {
            "result": "success",
            "messages": [],
        }

        wrapper.get_messages_raw(anchor="newest", num_before=10)

        mock_zulip_client.get_messages.assert_called()
        args = mock_zulip_client.get_messages.call_args[0][0]
        assert args["anchor"] == "newest"
        assert args["num_before"] == 10

    def test_get_messages_typed(self, mock_config_manager, mock_zulip_client):
        """Test getting typed messages."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)
        mock_zulip_client.get_messages.return_value = {
            "result": "success",
            "messages": [
                {
                    "id": 1,
                    "sender_full_name": "Alice",
                    "sender_email": "alice@example.com",
                    "timestamp": 1234567890,
                    "content": "hi",
                    "type": "stream",
                    "display_recipient": "general",
                    "subject": "topic",
                }
            ],
        }

        messages = wrapper.get_messages()
        assert len(messages) == 1
        assert isinstance(messages[0], ZulipMessage)
        assert messages[0].sender_full_name == "Alice"

    def test_get_streams_caching(self, mock_config_manager, mock_zulip_client):
        """Test get_streams uses cache."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)

        # Setup cache
        wrapper.stream_cache.set_streams([{"name": "cached"}])

        # Call should return cached
        result = wrapper.get_streams()
        assert result["streams"][0]["name"] == "cached"
        mock_zulip_client.get_streams.assert_not_called()

        # Force fresh
        mock_zulip_client.get_streams.return_value = {
            "result": "success",
            "streams": [{"name": "fresh"}],
        }
        result = wrapper.get_streams(force_fresh=True)
        assert result["streams"][0]["name"] == "fresh"
        mock_zulip_client.get_streams.assert_called()

    def test_upload_file_client_method(self, mock_config_manager, mock_zulip_client):
        """Test upload_file using client method if available."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)

        # Mock client having upload_file
        mock_zulip_client.upload_file.return_value = {
            "result": "success",
            "uri": "/user_uploads/file",
        }

        content = b"content"
        result = wrapper.upload_file(content, "test.txt")

        assert result["result"] == "success"
        mock_zulip_client.upload_file.assert_called()

    def test_upload_file_fallback(self, mock_config_manager, mock_zulip_client):
        """Test upload_file fallback to requests."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)

        # Remove upload_file from client mock
        del mock_zulip_client.upload_file

        # Mock requests.post
        # We need to make sure requests is importable even if not installed in env?
        # It is in dependencies.
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"uri": "url"}

            # We need client.email and api_key set
            mock_zulip_client.email = "test@example.com"
            mock_zulip_client.api_key = "key"
            mock_zulip_client.base_url = "https://chat.zulip.org"

            # Trigger property to set _base_url in wrapper
            _ = wrapper.client

            result = wrapper.upload_file(b"data", "file.txt")
            assert result["result"] == "success"
            mock_post.assert_called()

    def test_get_daily_summary(self, mock_config_manager, mock_zulip_client):
        """Test daily summary generation."""
        wrapper = ZulipClientWrapper(config_manager=mock_config_manager)

        # Mock get_messages_from_stream
        # It calls get_messages_raw internally. We can mock get_messages_raw or get_messages_from_stream.
        # Since get_messages_from_stream is cached, let's mock it on the instance or patch class.

        with patch.object(ZulipClientWrapper, "get_messages_from_stream") as mock_get:
            mock_get.return_value = {
                "result": "success",
                "messages": [
                    {"sender_full_name": "User1", "subject": "Topic1"},
                    {"sender_full_name": "User1", "subject": "Topic1"},
                    {"sender_full_name": "User2", "subject": "Topic2"},
                ],
            }

            summary = wrapper.get_daily_summary(streams=["general"])

            assert summary["total_messages"] == 3
            assert summary["top_senders"]["User1"] == 2
            assert summary["streams"]["general"]["topics"]["Topic1"] == 2


def test_get_messages_by_ids_and_empty_topic_flag():
    config = MagicMock()
    config.get_zulip_client_config.return_value = {
        "email": "owner@example.com",
        "api_key": "fake",
        "site": "https://example.com",
    }
    wrapper = ZulipClientWrapper(config)
    sdk = MagicMock(feature_level=513)
    sdk.get_messages.return_value = {"result": "success", "messages": []}
    wrapper._client = sdk

    wrapper.get_messages_by_ids([3, 4])
    assert sdk.get_messages.call_args[0][0] == {
        "message_ids": [3, 4],
        "apply_markdown": False,
        "allow_empty_topic_name": True,
    }

    sdk.feature_level = 300
    wrapper.get_messages_raw(use_cache=False)
    assert "allow_empty_topic_name" not in sdk.get_messages.call_args[0][0]


@pytest.mark.parametrize("level", [513, 300])
def test_get_users_by_ids_uses_server_filter_when_supported(level):
    config = MagicMock()
    config.get_zulip_client_config.return_value = {
        "email": "owner@example.com",
        "api_key": "fake",
        "site": "https://example.com",
    }
    wrapper = ZulipClientWrapper(config)
    sdk = MagicMock(feature_level=level)
    roster = [{"user_id": 1}, {"user_id": 2}, {"user_id": 3}]
    sdk.get_users.return_value = {"result": "success", "members": roster}
    wrapper._client = sdk

    result = wrapper.get_users(user_ids=[1, 3])

    request = sdk.get_users.call_args[0][0]
    if level >= 384:
        assert request["user_ids"] == [1, 3]
        assert result["members"] == roster
    else:
        assert "user_ids" not in request
        assert result["members"] == [{"user_id": 1}, {"user_id": 3}]
        # The full roster stays cached for the next caller.
        assert len(wrapper.get_users()["members"]) == 3
        assert sdk.get_users.call_count == 1


def test_daily_summary_uses_one_date_anchored_request():
    config = MagicMock()
    config.get_zulip_client_config.return_value = {
        "email": "owner@example.com",
        "api_key": "fake",
        "site": "https://example.com",
    }
    wrapper = ZulipClientWrapper(config)
    sdk = MagicMock(feature_level=513)
    now = datetime.now(timezone.utc).timestamp()
    sdk.get_messages.return_value = {
        "result": "success",
        "found_newest": False,
        "messages": [
            {
                "display_recipient": "a",
                "sender_full_name": "U1",
                "subject": "t",
                "timestamp": now,
            },
            {
                "display_recipient": "b",
                "sender_full_name": "U2",
                "subject": "t",
                "timestamp": now,
            },
            {
                "display_recipient": "a",
                "sender_full_name": "U1",
                "subject": "old",
                "timestamp": now - 3 * 86400,
            },
        ],
    }
    wrapper._client = sdk

    summary = wrapper.get_daily_summary(hours_back=24)

    sdk.get_messages.assert_called_once()
    sdk.get_streams.assert_not_called()
    request = sdk.get_messages.call_args[0][0]
    assert request["anchor"] == "date" and request["anchor_date"]
    assert request["narrow"] == [{"operator": "channels", "operand": "public"}]
    assert request["apply_markdown"] is False
    assert summary["total_messages"] == 2
    assert summary["streams"]["a"] == {"message_count": 1, "topics": {"t": 1}}
    assert summary["top_senders"] == {"U1": 1, "U2": 1}
    assert summary["truncated"] is True


def test_daily_summary_loops_per_stream_before_fl_445():
    config = MagicMock()
    config.get_zulip_client_config.return_value = {
        "email": "owner@example.com",
        "api_key": "fake",
        "site": "https://example.com",
    }
    wrapper = ZulipClientWrapper(config)
    sdk = MagicMock(feature_level=400)
    sdk.get_streams.return_value = {
        "result": "success",
        "streams": [{"name": "a"}, {"name": "secret", "invite_only": True}],
    }
    sdk.get_messages.return_value = {"result": "success", "messages": []}
    wrapper._client = sdk

    summary = wrapper.get_daily_summary()

    assert sdk.get_messages.call_count == 1
    assert sdk.get_messages.call_args[0][0]["narrow"] == [
        {"operator": "channel", "operand": "a"}
    ]
    assert summary["streams"] == {"a": {"message_count": 0, "topics": {}}}
