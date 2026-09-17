"""Account boundaries, query semantics, and lazy credential resolution."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from zulipchat_mcp import config
from zulipchat_mcp.core.cache import UserCache
from zulipchat_mcp.core.client import ZulipClientWrapper


@pytest.fixture
def manager(monkeypatch):
    for key in ("ZULIP_CONFIG_FILE", "ZULIP_BOT_CONFIG_FILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config.ConfigManager, "_find_default_config", lambda self: None)
    monkeypatch.setenv("ZULIP_EMAIL", "owner@example.com")
    monkeypatch.setenv("ZULIP_API_KEY", "user-key")
    monkeypatch.setenv("ZULIP_SITE", "https://user.example.com")
    monkeypatch.setenv("ZULIP_BOT_EMAIL", "bot@example.com")
    monkeypatch.setenv("ZULIP_BOT_API_KEY", "bot-key")
    return config.ConfigManager()


def test_file_credentials_override_sdk_environment(manager, tmp_path):
    path = tmp_path / "bot.zuliprc"
    path.write_text(
        "[api]\nemail=file-bot@example.com\nkey=file-key\nsite=https://bot.example.com\n"
    )
    manager.config.bot_config_file = str(path)
    # Exercise the real SDK constructor, mocking only its initial network request.
    with patch(
        "zulip.Client.get_server_settings", return_value={"zulip_version": "12.0"}
    ):
        wrapper = ZulipClientWrapper(manager, use_bot_identity=True)
        assert wrapper.client.email == "file-bot@example.com"
        assert wrapper.client.api_key == "file-key"
        assert wrapper.base_url == "https://bot.example.com"


def test_bot_env_credentials_can_use_user_file_site(manager, tmp_path):
    path = tmp_path / "user.zuliprc"
    path.write_text(
        "[api]\nemail=owner@example.com\nkey=file-key\nsite=https://file.example.com\n"
    )
    manager.config.config_file = str(path)
    manager.config.site = None
    credentials = manager.get_zulip_client_config(use_bot=True)
    assert credentials["email"] == "bot@example.com"
    assert credentials["site"] == "https://file.example.com"


def test_identity_caches_do_not_cross_accounts(manager):
    user = ZulipClientWrapper(manager)
    bot = ZulipClientWrapper(manager, use_bot_identity=True)
    user._client = MagicMock()
    bot._client = MagicMock()
    user._client.get_streams.return_value = {
        "result": "success",
        "streams": [{"name": "private"}],
    }
    bot._client.get_streams.return_value = {"result": "success", "streams": []}
    user._client.get_users.return_value = {
        "result": "success",
        "members": [{"email": "private@example.com"}],
    }
    bot._client.get_users.return_value = {"result": "success", "members": []}
    assert user.get_streams()["streams"]
    assert user.get_users()["members"]
    assert bot.get_streams()["streams"] == []
    assert bot.get_users()["members"] == []


def test_stream_filters_do_not_read_or_poison_default_cache(manager):
    wrapper = ZulipClientWrapper(manager)
    wrapper._client = MagicMock()
    wrapper._client.get_streams.side_effect = [
        {"result": "success", "streams": [{"name": "default"}]},
        {"result": "success", "streams": [{"name": "filtered"}]},
    ]
    assert wrapper.get_streams()["streams"][0]["name"] == "default"
    assert (
        wrapper.get_streams(include_subscribed=False)["streams"][0]["name"]
        == "filtered"
    )
    assert wrapper.get_streams()["streams"][0]["name"] == "default"


def test_get_client_reuses_only_matching_configuration_and_identity(
    manager, monkeypatch
):
    monkeypatch.setattr(config, "_config_manager", manager)
    monkeypatch.setattr(config, "_current_identity", "user")
    user = config.get_client()
    assert user is config.get_client()
    config.set_current_identity("bot")
    bot = config.get_client()
    assert bot is config.get_bot_client()
    assert bot is not user
    monkeypatch.setattr(config, "_config_manager", config.ConfigManager())
    assert config.get_client() is not bot


def test_search_failure_never_removes_search_constraint(manager):
    wrapper = ZulipClientWrapper(manager)
    wrapper.get_messages_raw = MagicMock(
        side_effect=[RuntimeError("search failed"), {"messages": ["unrelated"]}]
    )
    with pytest.raises(RuntimeError, match="search failed"):
        wrapper.search_messages("secret")
    assert wrapper.get_messages_raw.call_count == 1


def test_message_time_window_uses_utc(manager):
    wrapper = ZulipClientWrapper(manager)
    recent = {
        "id": 1,
        "timestamp": datetime(2026, 9, 16, 11, tzinfo=timezone.utc).timestamp(),
    }
    old = {
        "id": 2,
        "timestamp": datetime(2026, 9, 15, 11, tzinfo=timezone.utc).timestamp(),
    }
    wrapper.get_messages_raw = MagicMock(
        return_value={"result": "success", "messages": [old, recent]}
    )
    with patch("zulipchat_mcp.core.client.datetime", wraps=datetime) as clock:
        clock.now.return_value = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
        result = wrapper.get_messages_from_stream(hours_back=2)
        clock.now.assert_called_once_with(timezone.utc)
    assert wrapper.get_messages_raw.call_args.kwargs["anchor"] == "newest"
    assert result["messages"] == [recent]


def test_cold_user_cache_and_ambiguous_names_fail_closed():
    cache = UserCache()
    assert not cache.is_same_user("one@example.com", "two@example.com")
    assert not cache.is_same_user("", "")
    cache.set_users(
        [
            {
                "full_name": "Alex One",
                "email": "one@example.com",
                "delivery_email": "real@example.com",
            },
            {"full_name": "Alex Two", "email": "two@example.com"},
        ]
    )
    assert cache.resolve_user("Alex")["email"] is None
    assert cache.resolve_user("Alex One")["email"] == "one@example.com"
    assert cache.is_same_user("ONE@example.com", "REAL@example.com")
    cache.cache.clear()
    assert cache.resolve_user("Alex One")["email"] is None
    assert not cache.is_same_user("one@example.com", "real@example.com")
