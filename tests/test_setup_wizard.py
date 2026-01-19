"""Tests for setup_wizard.py."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.setup_wizard import (
    generate_claude_code_command,
    generate_mcp_config,
    get_mcp_client_config_path,
    scan_for_zuliprc_files,
    select_identity,
    validate_zuliprc,
    write_config_to_file,
)


class TestScanForZuliprcFiles:
    """Tests for scan_for_zuliprc_files."""

    @pytest.fixture
    def mock_home(self, tmp_path, monkeypatch):
        """Mock home directory."""
        monkeypatch.setenv("HOME", str(tmp_path))
        # Also need to patch Path.home() because in some envs it might not check env var directly or if python started before env set?
        # Python's Path.home() usually checks HOME.
        return tmp_path

    def test_finds_standard_locations(self, mock_home):
        """Test scanning ~/.zuliprc and ~/.config/zulip/zuliprc."""
        # Create .zuliprc
        (mock_home / ".zuliprc").write_text("[api]\nkey=123", encoding="utf-8")

        # Create .config/zulip/zuliprc
        config_dir = mock_home / ".config" / "zulip"
        config_dir.mkdir(parents=True)
        (config_dir / "zuliprc").write_text("[api]\nkey=456", encoding="utf-8")

        found = scan_for_zuliprc_files()
        found_paths = [str(p.resolve()) for p in found]

        assert str((mock_home / ".zuliprc").resolve()) in found_paths
        assert str((config_dir / "zuliprc").resolve()) in found_paths

    def test_finds_named_variants(self, mock_home):
        """Test finding .zuliprc-* pattern files."""
        (mock_home / ".zuliprc-dev").write_text("[api]\nkey=789", encoding="utf-8")
        found = scan_for_zuliprc_files()
        found_paths = [str(p.resolve()) for p in found]
        assert str((mock_home / ".zuliprc-dev").resolve()) in found_paths

    def test_validates_api_section_exists(self, mock_home):
        """Test that files without [api] section are ignored."""
        (mock_home / ".zuliprc-invalid").write_text("just some text", encoding="utf-8")
        found = scan_for_zuliprc_files()
        found_paths = [str(p.resolve()) for p in found]
        assert str((mock_home / ".zuliprc-invalid").resolve()) not in found_paths


class TestValidateZuliprc:
    """Tests for validate_zuliprc."""

    @pytest.fixture
    def mock_client_cls(self):
        with patch("src.zulipchat_mcp.setup_wizard.Client") as mock:
            yield mock

    def test_valid_credentials_user(self, mock_client_cls, tmp_path):
        """Test validation of valid user credentials."""
        # Setup mock
        client_instance = MagicMock()
        client_instance.get_profile.return_value = {
            "result": "success",
            "full_name": "Test User",
            "email": "user@example.com",
            "is_bot": False,
        }
        mock_client_cls.return_value = client_instance

        # Create dummy file
        zuliprc = tmp_path / "zuliprc"
        zuliprc.touch()

        result = validate_zuliprc(zuliprc, silent=True)

        assert result is not None
        assert result["name"] == "Test User"
        assert result["email"] == "user@example.com"
        assert result["is_bot"] is False
        assert result["path"] == str(zuliprc.resolve())

    def test_valid_credentials_bot(self, mock_client_cls, tmp_path):
        """Test validation of valid bot credentials."""
        client_instance = MagicMock()
        client_instance.get_profile.return_value = {
            "result": "success",
            "full_name": "Test Bot",
            "email": "bot@example.com",
            "is_bot": True,
        }
        mock_client_cls.return_value = client_instance

        zuliprc = tmp_path / "zuliprc"
        zuliprc.touch()

        result = validate_zuliprc(zuliprc, silent=True)

        assert result is not None
        assert result["is_bot"] is True

    def test_invalid_credentials(self, mock_client_cls, tmp_path):
        """Test handling of invalid credentials."""
        client_instance = MagicMock()
        client_instance.get_profile.return_value = {
            "result": "error",
            "msg": "Invalid API key",
        }
        mock_client_cls.return_value = client_instance

        zuliprc = tmp_path / "zuliprc"
        zuliprc.touch()

        result = validate_zuliprc(zuliprc, silent=True)
        assert result is None

    def test_file_not_found(self, tmp_path):
        """Test handling of missing file."""
        result = validate_zuliprc(tmp_path / "nonexistent", silent=True)
        assert result is None


class TestGenerateMcpConfig:
    """Tests for config generation."""

    def test_user_only_config(self):
        """Test config generation with user credentials only."""
        user_config = {"path": "/path/to/zuliprc"}
        config = generate_mcp_config(user_config)

        assert "uv" in config["command"]
        assert "zulipchat-mcp" in config["args"][1]
        assert "--zulip-config-file" in config["args"]
        assert "/path/to/zuliprc" in config["args"]
        assert "--zulip-bot-config-file" not in config["args"]

    def test_user_and_bot_config(self):
        """Test config generation with both identities."""
        user_config = {"path": "/path/to/user"}
        bot_config = {"path": "/path/to/bot"}
        config = generate_mcp_config(user_config, bot_config)

        assert "--zulip-bot-config-file" in config["args"]
        assert "/path/to/bot" in config["args"]

    def test_generate_claude_code_command(self):
        """Test claude code command generation."""
        user_config = {"path": "/path/to/user"}
        bot_config = {"path": "/path/to/bot"}
        cmd = generate_claude_code_command(user_config, bot_config)

        assert "claude mcp add zulipchat" in cmd
        assert "-e ZULIP_CONFIG_FILE=/path/to/user" in cmd
        assert "-e ZULIP_BOT_CONFIG_FILE=/path/to/bot" in cmd


class TestWriteConfigToFile:
    """Tests for write_config_to_file."""

    def test_creates_new_config(self, tmp_path):
        """Test creating new config file."""
        config_path = tmp_path / "config.json"
        mcp_config = {"command": "test"}

        success = write_config_to_file(config_path, "server", mcp_config)

        assert success is True
        assert config_path.exists()

        content = json.loads(config_path.read_text())
        assert content["mcpServers"]["server"] == mcp_config

    def test_merges_with_existing(self, tmp_path):
        """Test merging with existing config."""
        config_path = tmp_path / "config.json"
        existing = {"mcpServers": {"other": {}}}
        config_path.write_text(json.dumps(existing))

        mcp_config = {"command": "test"}
        write_config_to_file(config_path, "server", mcp_config)

        content = json.loads(config_path.read_text())
        assert "other" in content["mcpServers"]
        assert "server" in content["mcpServers"]

    def test_creates_backup(self, tmp_path):
        """Test that backup is created."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")

        write_config_to_file(config_path, "server", {})

        backup = tmp_path / "config.json.bak"
        assert backup.exists()


class TestHelpers:
    """Tests for helper functions."""

    def test_get_mcp_client_config_path(self, monkeypatch, tmp_path):
        """Test path resolution."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Claude Desktop (linux fallback)
        if sys.platform not in ["darwin", "win32"]:
            expected = tmp_path / ".config" / "Claude" / "claude_desktop_config.json"
            assert get_mcp_client_config_path("claude-desktop") == expected

        # Gemini (creates default path if not exists)
        expected = tmp_path / ".gemini" / "settings.json"
        assert get_mcp_client_config_path("gemini") == expected

    def test_select_identity_manual_entry(self, monkeypatch):
        """Test selecting identity with manual entry."""
        monkeypatch.setattr("builtins.input", lambda _: "/manual/path")

        with patch("src.zulipchat_mcp.setup_wizard.validate_zuliprc") as mock_validate:
            mock_validate.return_value = {"valid": True}

            # Empty list triggers manual entry prompt immediately?
            # No, logic says: if not available: prompt(Enter path...)

            result = select_identity([], "User")
            assert result == {"valid": True}
            mock_validate.assert_called()
