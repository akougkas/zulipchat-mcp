"""Tests for integrations registry CLI."""

import json
import shlex
import sys

import pytest

from src.zulipchat_mcp import __version__
from src.zulipchat_mcp.integrations import registry


def test_shell_snippets_preserve_metacharacters():
    value = '/some path/$(touch marker)/`command`/"zuliprc"'
    base = registry._build_base_config(value, None, False)
    assert shlex.split(registry._render_for_client("claude-code", base)) == [
        "claude",
        "mcp",
        "add",
        "zulipchat",
        "--",
        "uvx",
        *base["args"],
    ]
    assert shlex.split(
        registry._render_remote_for_client("claude-code", value, value)
    ) == [
        "claude",
        "mcp",
        "add",
        "--transport",
        "http",
        "zulipchat",
        value,
        "--header",
        f"Authorization: Bearer {value}",
    ]


def test_codex_snippet_round_trips_escaped_paths():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    value = 'C:\\Users\\name "quoted"\\zuliprc\nline'
    base = registry._build_base_config(value, None, False)
    parsed = tomllib.loads(registry._render_for_client("codex", base))
    assert parsed["mcp_servers"]["zulipchat"] == base


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


def test_print_remote_generic_with_token(monkeypatch, capsys):
    """Remote generic snippet should carry the HTTP url and bearer header."""
    _run_main(
        monkeypatch,
        [
            "print",
            "--client",
            "generic",
            "--remote-url",
            "http://mcp.internal:8000/mcp",
            "--remote-token",
            "tok123",
        ],
    )
    payload = json.loads(capsys.readouterr().out)
    server = payload["mcpServers"]["zulipchat"]
    assert server["type"] == "http"
    assert server["url"] == "http://mcp.internal:8000/mcp"
    assert server["headers"]["Authorization"] == "Bearer tok123"


def test_print_remote_vscode_without_token(monkeypatch, capsys):
    """Remote snippets omit the Authorization header when no token is set."""
    monkeypatch.delenv("ZULIPCHAT_HTTP_AUTH_TOKEN", raising=False)
    _run_main(
        monkeypatch,
        ["print", "--client", "vscode", "--remote-url", "http://mcp.internal:8000/mcp"],
    )
    payload = json.loads(capsys.readouterr().out)
    server = payload["servers"]["zulipchat"]
    assert server["type"] == "http"
    assert "headers" not in server


def test_print_remote_rejects_unsupported_client(monkeypatch, capsys):
    """Clients without a known remote format exit with a CLI error, not a traceback."""
    with pytest.raises(SystemExit):
        _run_main(
            monkeypatch,
            ["print", "--client", "cursor", "--remote-url", "http://x:8000/mcp"],
        )
    assert "Remote HTTP snippets" in capsys.readouterr().err


def test_print_requires_config_file_for_local(monkeypatch):
    """Local stdio snippets still require --zulip-config-file."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, ["print", "--client", "generic"])


def test_export_claude_code_standalone_merges_mcp_json(monkeypatch, capsys, tmp_path):
    """Standalone export merges .mcp.json and adds the portable skill."""
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "other"}}}), encoding="utf-8"
    )
    _run_main(
        monkeypatch,
        [
            "export",
            "--client",
            "claude-code",
            "--mode",
            "standalone",
            "--output-dir",
            str(tmp_path),
            "--zulip-config-file",
            "/home/test/.zuliprc",
            "--server-id",
            "zulipchat-grc",
        ],
    )
    assert json.loads(capsys.readouterr().out)["status"] == "success"
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert set(servers) == {"other", "zulipchat-grc"}
    assert (tmp_path / ".claude/skills/zulipchat/SKILL.md").exists()
    assert not (tmp_path / ".claude/settings.json").exists()


def test_export_claude_code_plugin_writes_modern_layout(monkeypatch, capsys, tmp_path):
    """Plugin export should write Anthropic's current plugin structure."""
    _run_main(
        monkeypatch,
        [
            "export",
            "--client",
            "claude-code",
            "--mode",
            "plugin",
            "--output-dir",
            str(tmp_path),
            "--zulip-config-file",
            "/home/test/.zuliprc",
            "--zulip-bot-config-file",
            "/home/test/.zuliprc-bot",
            "--extended-tools",
        ],
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"

    manifest = json.loads(
        (tmp_path / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "zulipchat"
    assert manifest["version"] == __version__

    assert "$schema" not in manifest

    mcp_config = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert set(mcp_config) == {"mcpServers"}
    assert mcp_config["mcpServers"]["zulipchat"]["type"] == "stdio"
    assert "--extended-tools" in mcp_config["mcpServers"]["zulipchat"]["args"]
    assert (tmp_path / "skills" / "zulipchat" / "SKILL.md").exists()
    assert not (tmp_path / "hooks").exists()
