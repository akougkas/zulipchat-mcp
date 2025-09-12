"""Tests for ConfigManager behavior using environment variables only."""

from __future__ import annotations

import os

import pytest

from zulipchat_mcp.config import ConfigManager


def _set_env(email="user@example.com", api_key="apikeyapikey", site="https://zulip.example"):
    os.environ["ZULIP_EMAIL"] = email
    os.environ["ZULIP_API_KEY"] = api_key
    os.environ["ZULIP_SITE"] = site


def test_config_manager_validates_and_bot_config(monkeypatch) -> None:
    _set_env()
    os.environ["ZULIP_BOT_EMAIL"] = "bot@example.com"
    os.environ["ZULIP_BOT_API_KEY"] = "botapikeyapikey"
    cm = ConfigManager()
    assert cm.validate_config() is True
    assert cm.has_bot_credentials() is True
    bot_cfg = cm.get_zulip_client_config(use_bot=True)
    assert bot_cfg["email"] == "bot@example.com"


def test_config_manager_errors_and_defaults(monkeypatch) -> None:
    # Clear env to trigger errors
    for k in ["ZULIP_EMAIL", "ZULIP_API_KEY", "ZULIP_SITE"]:
        os.environ.pop(k, None)

    with pytest.raises(ValueError):
        ConfigManager(email=None)

    # Provide via env again; port/debug fallbacks
    _set_env()
    os.environ["MCP_PORT"] = "not-an-int"
    os.environ["MCP_DEBUG"] = "true"
    cm = ConfigManager()
    assert cm.config.port == 3000  # fallback on invalid port
    assert cm.config.debug is True
    # With bot creds set, use_bot returns bot creds
    user_cfg = cm.get_zulip_client_config(use_bot=True)
    assert user_cfg["email"] == os.environ["ZULIP_BOT_EMAIL"]

    # Clear bot env; has_bot_credentials should be False
    os.environ.pop("ZULIP_BOT_EMAIL", None)
    os.environ.pop("ZULIP_BOT_API_KEY", None)
    cm2 = ConfigManager()
    assert cm2.has_bot_credentials() is False
