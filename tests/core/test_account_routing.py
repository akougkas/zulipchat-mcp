"""Selected credentials must not be routed using an unrelated ambient realm."""

from unittest.mock import MagicMock, patch

from zulipchat_mcp.config import ConfigManager
from zulipchat_mcp.core.client import ZulipClientWrapper


def test_environment_bot_uses_selected_user_realm_in_sdk_constructor(
    monkeypatch, tmp_path
):
    credential = tmp_path / "zuliprc"
    credential.write_text(
        "[api]\nemail=owner@selected.example\nkey=user-key\nsite=https://selected.example\n"
    )
    for key in ("ZULIP_CONFIG_FILE", "ZULIP_BOT_CONFIG_FILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ZULIP_SITE", "https://ambient.example")
    monkeypatch.setenv("ZULIP_BOT_EMAIL", "bot@selected.example")
    monkeypatch.setenv("ZULIP_BOT_API_KEY", "bot-key")
    manager = ConfigManager(config_file=str(credential))
    assert manager.get_zulip_client_config(True)["site"] == "https://selected.example"
    with patch("zulipchat_mcp.core.client.Client", return_value=MagicMock()) as sdk:
        wrapper = ZulipClientWrapper(manager, use_bot_identity=True)
        _ = wrapper.client
        assert sdk.call_args.kwargs["site"] == "https://selected.example"
        assert sdk.call_args.kwargs["email"] == "bot@selected.example"
        assert sdk.call_args.kwargs["api_key"] == "bot-key"


def test_separate_bot_file_retains_its_explicit_realm(monkeypatch, tmp_path):
    user, bot = tmp_path / "user", tmp_path / "bot"
    user.write_text(
        "[api]\nemail=owner@example.com\nkey=u\nsite=https://selected.example\n"
    )
    bot.write_text("[api]\nemail=bot@example.com\nkey=b\nsite=https://bot.example\n")
    for key in ("ZULIP_CONFIG_FILE", "ZULIP_BOT_CONFIG_FILE"):
        monkeypatch.delenv(key, raising=False)
    manager = ConfigManager(config_file=str(user), bot_config_file=str(bot))
    assert manager.get_zulip_client_config(True)["site"] == "https://bot.example"
    first = manager.resolved_account().fingerprint
    user.write_text(
        user.read_text().replace("https://selected.example", "https://other.example")
    )
    assert manager.resolved_account().fingerprint != first
