"""Installation security checks must catch shell spelling variations."""

import json

import pytest

from scripts import release_preflight


@pytest.mark.parametrize(
    "command,passes",
    [
        ("uvx zulipchat-mcp-agents --zulip-config-file /tmp/zuliprc", False),
        ("uvx --python 3.12 zulipchat-mcp-integrate list", False),
        ("uvx --from '' zulipchat-mcp-agents --help", False),
        ("uvx --from= zulipchat-mcp-setup", False),
        ("uvx --from zulipchat-mcp zulipchat-mcp-agents --help", True),
        ("uvx --from=zulipchat-mcp zulipchat-mcp-integrate list", True),
        ("uvx --from 'zulipchat-mcp==0.7.4' zulipchat-mcp-setup", True),
        ("uvx \\\n  --from zulipchat-mcp \\\n  zulipchat-mcp-agents --help", True),
        ("uvx zulipchat-mcp --zulip-config-file /tmp/zuliprc", True),
    ],
)
def test_companion_commands_require_nonempty_package_source(
    tmp_path, monkeypatch, command, passes
):
    monkeypatch.setattr(release_preflight, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(f"```bash\n{command}\n```\n")
    assert release_preflight._check_uvx_package_sources().passed is passes


@pytest.mark.parametrize(
    "args,passes",
    [
        (["zulipchat-mcp-agents", "--help"], False),
        (["--python", "3.10", "zulipchat-mcp-integrate", "list"], False),
        (["zulipchat-mcp-agents", "--from", "zulipchat-mcp"], False),
        (["--from", "", "zulipchat-mcp-agents"], False),
        (["--from", "zulipchat-mcp", "zulipchat-mcp-agents", "--help"], True),
        (["--from=zulipchat-mcp", "zulipchat-mcp-integrate", "list"], True),
        (["zulipchat-mcp", "--extended-tools"], True),
    ],
)
def test_json_command_arrays_require_source_before_companion(
    tmp_path, monkeypatch, args, passes
):
    monkeypatch.setattr(release_preflight, "ROOT", tmp_path)
    templates = tmp_path / "integrations" / "test"
    templates.mkdir(parents=True)
    (templates / "mcp.json").write_text(
        json.dumps({"mcpServers": {"zulipchat": {"command": "uvx", "args": args}}})
    )
    assert release_preflight._check_uvx_package_sources().passed is passes


def test_integration_versions_cover_the_pancode_pack(tmp_path, monkeypatch):
    monkeypatch.setattr(release_preflight, "ROOT", tmp_path)
    (tmp_path / "integrations").mkdir()
    (tmp_path / "pancode").mkdir()
    (tmp_path / "pancode" / "plugin.json").write_text('{"version": "0.8.0"}')
    result = release_preflight._check_integration_versions("0.8.1")
    assert not result.passed
    assert result.detail == "pancode/plugin.json"
