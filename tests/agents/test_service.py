"""The bridge as a background service, and `add` reaching the running bridge."""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from zulipchat_mcp.agents import cli, service


@pytest.fixture
def systemd(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("PATH", "/home/me/.nvm/bin:/usr/bin")
    calls: list[tuple[str, ...]] = []

    def run(*argv: str) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "active", "")

    monkeypatch.setattr(service, "_run", run)
    return calls


def test_install_writes_a_unit_with_the_shell_path_and_starts_it(systemd, tmp_path):
    note = service.install()
    unit = (tmp_path / "config/systemd/user/zulipchat-mcp-agents.service").read_text()
    assert f"ExecStart={sys.executable} -m zulipchat_mcp.agents.cli run" in unit
    # Node agents (#!/usr/bin/env node) need the shell's PATH under systemd.
    assert 'Environment="PATH=/home/me/.nvm/bin:/usr/bin"' in unit
    assert "RestartPreventExitStatus=78" in unit and "KillMode=mixed" in unit
    assert systemd == [
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "zulipchat-mcp-agents"),
        ("systemctl", "--user", "restart", "zulipchat-mcp-agents"),
    ]
    assert "starts at login" in note and service.installed()
    assert "removed" in service.uninstall() and not service.installed()


def test_a_uvx_environment_is_refused(systemd, monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/home/me/.cache/uv/archive-v0/aqP2/")
    with pytest.raises(service.ServiceError, match="uv tool install"):
        service.install()
    assert systemd == []


def test_launchd_plist_keeps_the_bridge_alive_with_the_shell_path():
    plist = plistlib.loads(service.render_launchd(["/py", "-m", "x", "run"], "/a:/b"))
    assert plist["ProgramArguments"] == ["/py", "-m", "x", "run"]
    assert plist["EnvironmentVariables"] == {"PATH": "/a:/b"}
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] == {"SuccessfulExit": False}


def test_other_platforms_are_told_to_keep_run_open(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert not service.installed()
    with pytest.raises(service.ServiceError, match="run"):
        service.install()


def test_add_restarts_an_installed_bridge(systemd, monkeypatch, tmp_path, capsys):
    service.unit_path().parent.mkdir(parents=True)
    service.unit_path().write_text("[Unit]\n")
    bot = tmp_path / "bot.zuliprc"
    bot.write_text("[api]\nemail=b@x\nkey=k\nsite=https://x\n")
    status = cli.main(
        ["add", "pancode", "--bot-zuliprc", str(bot), "--cwd", str(tmp_path)]
    )
    assert status == 0
    assert ("systemctl", "--user", "restart", "zulipchat-mcp-agents") in systemd
    assert "Restarted the bridge" in capsys.readouterr().out


def test_add_creates_the_bot_with_the_default_zuliprc(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(cli, "DEFAULT_ZULIPRC", tmp_path / "missing")
    assert cli.main(["add", "claude", "--cwd", str(tmp_path)]) == 1
    assert "Download your zuliprc" in capsys.readouterr().err
    assert not (tmp_path / "config/zulipchat-mcp/agents/claude.toml").exists()


def test_service_install_needs_an_agent(systemd, capsys):
    assert cli.main(["service", "install"]) == 1
    assert "add one first" in capsys.readouterr().err
    assert systemd == []
    assert not Path(service.unit_path()).exists()
