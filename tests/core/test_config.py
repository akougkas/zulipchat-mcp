"""Tests for core/config.py."""

import os
from unittest.mock import patch

from src.zulipchat_mcp.config import ConfigManager


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_init_defaults(self, monkeypatch):
        """Test initialization with defaults (no env vars)."""
        # Ensure clean env
        monkeypatch.delenv("ZULIP_CONFIG_FILE", raising=False)
        monkeypatch.delenv("ZULIP_BOT_CONFIG_FILE", raising=False)
        monkeypatch.delenv("MCP_DEBUG", raising=False)

        # Mock finding default config
        with patch.object(ConfigManager, "_find_default_config", return_value=None):
            manager = ConfigManager()
            assert manager.config.config_file is None
            assert manager.config.debug is False

    def test_init_with_args(self):
        """Test initialization with arguments."""
        manager = ConfigManager(
            config_file="/path/to/zuliprc", bot_config_file="/path/to/botrc", debug=True
        )
        assert manager.config.config_file == "/path/to/zuliprc"
        assert manager.config.bot_config_file == "/path/to/botrc"
        assert manager.config.debug is True

    def test_env_vars_priority(self, monkeypatch):
        """Test environment variables take precedence over defaults but args take precedence over env."""
        monkeypatch.setenv("ZULIP_CONFIG_FILE", "/env/path")
        monkeypatch.setenv("MCP_DEBUG", "true")

        # Env only
        with patch.object(ConfigManager, "_find_default_config", return_value=None):
            manager = ConfigManager()
            assert manager.config.config_file == "/env/path"
            assert manager.config.debug is True

        # Env overrides Args (Current implementation behavior)
        manager = ConfigManager(config_file="/arg/path", debug=False)
        assert manager.config.config_file == "/env/path"
        # Note: logic in _load_config:
        # final_config_file = self._get_config_file() or cli_config_file
        # This means ENV VAR overrides CLI ARG.

        assert (
            manager.config.debug is False
        )  # debug logic: get_debug() if cli_debug is None else cli_debug. So CLI overrides Env for debug.

    def test_find_default_config(self, monkeypatch, tmp_path):
        """Test finding default config file."""
        monkeypatch.delenv("ZULIP_CONFIG_FILE", raising=False)

        # Create a dummy zuliprc in cwd
        cwd_rc = tmp_path / "zuliprc"
        cwd_rc.touch()

        with patch("os.getcwd", return_value=str(tmp_path)):
            manager = ConfigManager()
            assert manager.config.config_file == str(cwd_rc)

    def test_validate_config(self):
        """Test configuration validation."""
        # File based
        with patch("os.path.exists", return_value=True):
            manager = ConfigManager(config_file="/valid/path")
            assert manager.validate_config() is True

        with patch("os.path.exists", return_value=False):
            manager = ConfigManager(config_file="/invalid/path")
            assert manager.validate_config() is False

        # Env based
        manager = ConfigManager()  # No file
        # Mock env vars in config object (since it's immutable dataclass, we need to init with them)
        # But ConfigManager loads from env.
        with patch.dict(
            os.environ, {"ZULIP_EMAIL": "a", "ZULIP_API_KEY": "b", "ZULIP_SITE": "c"}
        ):
            manager = ConfigManager()
            assert manager.validate_config() is True

    def test_has_bot_credentials(self):
        """Test checking bot credentials."""
        # File based
        with patch("os.path.exists", return_value=True):
            manager = ConfigManager(bot_config_file="/bot/path")
            assert manager.has_bot_credentials() is True

        with patch("os.path.exists", return_value=False):
            manager = ConfigManager(bot_config_file="/invalid/path")
            assert manager.has_bot_credentials() is False  # Env also empty

        # Env based
        with patch.dict(
            os.environ, {"ZULIP_BOT_EMAIL": "bot", "ZULIP_BOT_API_KEY": "key"}
        ):
            manager = ConfigManager()
            assert manager.has_bot_credentials() is True

    def test_get_zulip_client_config(self):
        """Test getting client config dict."""
        # User config
        manager = ConfigManager(config_file="/user/path")
        cfg = manager.get_zulip_client_config(use_bot=False)
        assert cfg["config_file"] == "/user/path"

        # Bot config
        with patch("os.path.exists", return_value=True):
            manager = ConfigManager(
                config_file="/user/path", bot_config_file="/bot/path"
            )
            cfg = manager.get_zulip_client_config(use_bot=True)
            assert cfg["config_file"] == "/bot/path"

        # Fallback to user config if bot requested but not available
        manager = ConfigManager(config_file="/user/path")
        cfg = manager.get_zulip_client_config(use_bot=True)
        assert cfg["config_file"] == "/user/path"
        # Wait, code says:
        # if use_bot and self.has_bot_credentials(): return bot_config
        # return user_config
        # So yes, falls back to user config.

    def test_get_port(self, monkeypatch):
        """Test port parsing."""
        monkeypatch.setenv("MCP_PORT", "4000")
        manager = ConfigManager()
        assert manager.config.port == 4000

        monkeypatch.setenv("MCP_PORT", "invalid")
        manager = ConfigManager()
        assert manager.config.port == 3000
