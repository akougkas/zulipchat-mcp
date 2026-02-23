"""Tests for integrations registry CLI."""

import json
import sys

import pytest

from src.zulipchat_mcp import __version__
from src.zulipchat_mcp.integrations import registry


def _run_main(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["zulipchat-mcp-integrate", *args])
    registry.main()


def test_list_outputs_all_clients(monkeypatch, capsys):
    """The list command should print all supported client ids."""
    _run_main(monkeypatch, ["list"])
    output = capsys.readouterr().out.strip().splitlines()
    assert output == registry.CLIENTS


def test_print_codex_includes_extended_flag(monkeypatch, capsys):
    """Codex render should be TOML and include extended flag when requested."""
    _run_main(
        monkeypatch,
        [
            "print",
            "--client",
            "codex",
            "--zulip-config-file",
            "/home/test/.zuliprc",
            "--extended-tools",
        ],
    )
    output = capsys.readouterr().out
    assert "[mcp_servers.zulipchat]" in output
    assert 'command = "uvx"' in output
    assert '"--extended-tools"' in output


def test_print_vscode_returns_servers_shape(monkeypatch, capsys):
    """VS Code render should use `servers` key with stdio type."""
    _run_main(
        monkeypatch,
        [
            "print",
            "--client",
            "vscode",
            "--zulip-config-file",
            "/home/test/.zuliprc",
        ],
    )
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert "servers" in payload
    assert payload["servers"]["zulipchat"]["type"] == "stdio"
    assert payload["servers"]["zulipchat"]["command"] == "uvx"


def test_version_flag(monkeypatch, capsys):
    """Version action should exit with code 0 and print version."""
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert __version__ in out
