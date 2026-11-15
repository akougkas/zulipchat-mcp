"""Tests for ConfigManager behavior using environment variables only."""

from __future__ import annotations

import os

from zulipchat_mcp.config import ConfigManager


def _set_env(
    email="user@example.com", api_key="apikeyapikey", site="https://zulip.example"
):
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
    # Clear env to trigger validation failure
    for k in ["ZULIP_EMAIL", "ZULIP_API_KEY", "ZULIP_SITE", "ZULIP_CONFIG_FILE"]:
        os.environ.pop(k, None)
    monkeypatch.setattr(ConfigManager, "_find_default_config", lambda _: None)

    # Without credentials, validation should fail (not raise)
    cm_no_creds = ConfigManager()
    assert cm_no_creds.validate_config() is False

    # Provide via env again; port/debug fallbacks
    _set_env()
    os.environ["MCP_PORT"] = "not-an-int"
    os.environ["MCP_DEBUG"] = "true"
    cm = ConfigManager()
    assert cm.config.port == 3000  # fallback on invalid port
    assert cm.config.debug is True

    # Clear bot env; has_bot_credentials should be False
    os.environ.pop("ZULIP_BOT_EMAIL", None)
    os.environ.pop("ZULIP_BOT_API_KEY", None)
    cm2 = ConfigManager()
    assert cm2.has_bot_credentials() is False


def test_blank_env_vars_do_not_shadow_config_file(monkeypatch, tmp_path) -> None:
    """A templated .env leaves keys like `ZULIP_SITE=` empty.

    Exporting "" would shadow an explicit --zulip-config-file, because the Zulip
    SDK reads these variables whenever the constructor arg is None. Blank values
    must be treated as unset.
    """
    zuliprc = tmp_path / "zuliprc"
    zuliprc.write_text(
        "[api]\nemail=me@example.com\nkey=secret\nsite=https://example.zulipchat.com\n"
    )

    for key in (
        "ZULIP_EMAIL",
        "ZULIP_API_KEY",
        "ZULIP_SITE",
        "ZULIP_BOT_EMAIL",
        "ZULIP_BOT_API_KEY",
        "ZULIP_CONFIG_FILE",
        "ZULIP_BOT_CONFIG_FILE",
    ):
        monkeypatch.setenv(key, "")

    cm = ConfigManager(config_file=str(zuliprc))

    assert cm.config.site is None
    assert cm.config.email is None
    assert cm.config.api_key is None
    # The explicitly passed config file survives the blank env vars.
    assert cm.config.config_file == str(zuliprc)
    assert cm.validate_config() is True
    assert cm.has_bot_credentials() is False


def _import_config_in(directory, environment):
    import json
    import subprocess
    import sys

    wanted = (
        "ZULIP_CONFIG_FILE ZULIP_EMAIL ZULIP_API_KEY ZULIP_SITE ZULIP_BOT_EMAIL "
        "ZULIP_BOT_API_KEY HTTPS_PROXY REQUESTS_CA_BUNDLE ZULIP_ALLOW_INSECURE "
        "ZULIPCHAT_MENTION_ALLOW ZULIPCHAT_DB_PATH"
    )
    script = (
        "import json, os, zulipchat_mcp.config; "
        f"print(json.dumps({{k: os.environ.get(k) for k in {wanted.split()!r}}}))"
    )
    clean = {k: v for k, v in os.environ.items() if not k.startswith("ZULIP")}
    for key in ("HTTPS_PROXY", "REQUESTS_CA_BUNDLE"):
        clean.pop(key, None)
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=directory,
        env={**clean, **environment},
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v for k, v in json.loads(done.stdout).items() if v is not None}


def test_dotenv_in_the_working_directory_supplies_credentials_and_nothing_else(
    tmp_path,
) -> None:
    (tmp_path / ".env").write_text(
        "ZULIP_CONFIG_FILE=./planted.zuliprc\n"
        "HTTPS_PROXY=http://evil.example:8080\n"
        "REQUESTS_CA_BUNDLE=./ca.pem\n"
        "ZULIP_ALLOW_INSECURE=true\n"
        "ZULIPCHAT_MENTION_ALLOW=everyone\n"
        "ZULIPCHAT_DB_PATH=./planted.duckdb\n"
        "ZULIP_EMAIL=dev@example.com\nZULIP_API_KEY=devkey\n"
        "ZULIP_SITE=https://dev.example.com\n"
        "ZULIP_BOT_EMAIL=bot@example.com\nZULIP_BOT_API_KEY=botkey\n"
    )
    assert _import_config_in(tmp_path, {}) == {
        "ZULIP_EMAIL": "dev@example.com",
        "ZULIP_API_KEY": "devkey",
        "ZULIP_SITE": "https://dev.example.com",
        "ZULIP_BOT_EMAIL": "bot@example.com",
        "ZULIP_BOT_API_KEY": "botkey",
    }
    # A real key is never paired with a site from the file, in either set.
    real = {"ZULIP_EMAIL": "me@example.com", "ZULIP_API_KEY": "realkey"}
    assert _import_config_in(tmp_path, real) == {
        **real,
        "ZULIP_BOT_EMAIL": "bot@example.com",
        "ZULIP_BOT_API_KEY": "botkey",
    }
    bot = {"ZULIP_BOT_API_KEY": "realbotkey"}
    assert _import_config_in(tmp_path, bot) == bot
