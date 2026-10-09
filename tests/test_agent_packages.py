"""Validate real host formats and preserve user-owned export destinations."""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from zulipchat_mcp.integrations.agent_package import (
    LAYOUTS,
    _parse,
    export_agent_package,
)
from zulipchat_mcp.integrations.claude_code_package import export_claude_code_package
from zulipchat_mcp.integrations.package_writer import write_package


@pytest.mark.parametrize("client", list(LAYOUTS))
def test_host_exports_are_parseable_and_have_portable_skills(tmp_path, client):
    export_agent_package(
        tmp_path,
        client=client,
        zulip_config_file="/home/test/.zuliprc",
        extended_tools=True,
    )
    config_path, skill_root, key = LAYOUTS[client]
    config = _parse((tmp_path / config_path).read_text(), Path(config_path).suffix)
    if client == "clio-coder":
        assert config["version"] == 1
        server = config["servers"][0]
        assert server["id"] == "zulipchat"
        assert "actionClass" not in server
    else:
        server = config[key]["zulipchat"]
    command = server.get("command", [])
    arguments = command if isinstance(command, list) else server["args"]
    assert "--extended-tools" in arguments
    for skill in (tmp_path / skill_root).glob("*/SKILL.md"):
        metadata = yaml.safe_load(skill.read_text().split("---", 2)[1])
        assert metadata["name"] == skill.parent.name
        assert metadata["description"]
    assert len(list((tmp_path / skill_root).glob("*/SKILL.md"))) == 4


@pytest.mark.parametrize(
    "client", ["codex", "opencode", "copilot", "vscode", "antigravity-cli", "generic"]
)
def test_exports_preserve_other_servers_and_refuse_identity_replacement(
    tmp_path, client
):
    config_path, _, key = LAYOUTS[client]
    destination = tmp_path / config_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    from zulipchat_mcp.integrations.agent_package import _serialize

    destination.write_text(
        _serialize(
            {key: {"other": {"command": "keep-me"}}, "user_setting": "keep"},
            destination.suffix,
        )
    )
    export_agent_package(tmp_path, client=client, zulip_config_file="/home/test/one")
    config = _parse(destination.read_text(), destination.suffix)
    assert config[key]["other"]["command"] == "keep-me"
    assert config["user_setting"] == "keep"
    before = destination.read_text()
    with pytest.raises(FileExistsError):
        export_agent_package(
            tmp_path, client=client, zulip_config_file="/home/test/two"
        )
    assert destination.read_text() == before
    export_agent_package(
        tmp_path, client=client, zulip_config_file="/home/test/two", force=True
    )
    assert "two" in destination.read_text()


def test_clio_export_preserves_other_servers_and_detects_duplicate_ids(tmp_path):
    destination = tmp_path / ".clio-coder/mcp.yaml"
    destination.parent.mkdir()
    destination.write_text(
        "version: 1\nservers:\n  - id: other\n    command: keep-me\n"
    )
    export_agent_package(
        tmp_path, client="clio-coder", zulip_config_file="/home/test/.zuliprc"
    )
    payload = yaml.safe_load(destination.read_text())
    assert payload["servers"][0] == {"id": "other", "command": "keep-me"}
    payload["servers"].append(payload["servers"][1])
    destination.write_text(yaml.safe_dump(payload))
    with pytest.raises(ValueError, match="Duplicate"):
        export_agent_package(
            tmp_path,
            client="clio-coder",
            zulip_config_file="/home/test/.zuliprc",
            force=True,
        )


def test_export_conflict_does_not_partially_change_claude_settings(tmp_path):
    settings = tmp_path / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text('{"theme":"keep"}')
    skill = tmp_path / ".claude/skills/zulipchat-loop/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("User-edited instructions")
    with pytest.raises(FileExistsError):
        export_claude_code_package(tmp_path, zulip_config_file="/home/test/.zuliprc")
    assert settings.read_text() == '{"theme":"keep"}'
    assert not (tmp_path / ".mcp.json").exists()


@pytest.mark.parametrize("client", ["codex", "clio-coder", "opencode"])
def test_export_refuses_symlinks_even_with_force(tmp_path, client):
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "project"
    output.mkdir()
    (output / LAYOUTS[client][1].split("/")[0]).symlink_to(
        outside, target_is_directory=True
    )
    with pytest.raises(ValueError, match="symlink"):
        export_agent_package(
            output, client=client, zulip_config_file="/home/test/.zuliprc", force=True
        )
    assert not list(outside.iterdir())


def test_package_writer_rejects_path_escape_and_preflights_all_conflicts(tmp_path):
    with pytest.raises(ValueError, match="inside"):
        write_package(tmp_path, {"../escape.md": "bad"})
    (tmp_path / "existing.md").write_text("user content")
    with pytest.raises(FileExistsError):
        write_package(tmp_path, {"new.md": "first", "existing.md": "replacement"})
    assert not (tmp_path / "new.md").exists()


def test_opencode_export_refuses_competing_jsonc_configuration(tmp_path):
    (tmp_path / "opencode.jsonc").write_text('{/* user comments */ "mcp": {}}')
    with pytest.raises(ValueError, match="competing"):
        export_agent_package(
            tmp_path, client="opencode", zulip_config_file="/home/test/.zuliprc"
        )


def test_portable_plugin_matches_published_schemas(tmp_path):
    export_agent_package(
        tmp_path,
        client="clio-coder",
        mode="plugin",
        zulip_config_file="/home/test/.zuliprc",
        extended_tools=True,
    )
    schemas = Path(__file__).parent / "fixtures/agent-plugins-1.0.0"
    for name in ("plugin", "mcp"):
        schema = json.loads((schemas / f"{name}.schema.json").read_text())
        jsonschema.Draft202012Validator(schema).validate(
            json.loads((tmp_path / f"{name}.json").read_text())
        )
    assert len(list((tmp_path / "skills").glob("*/SKILL.md"))) == 4
    assert not (tmp_path / "hooks").exists()


def test_claude_reexport_replaces_owned_hooks_and_preserves_unrelated_commands(
    tmp_path,
):
    export_claude_code_package(
        tmp_path,
        zulip_config_file="/realm-a/user",
        zulip_bot_config_file="/realm-a/bot",
    )
    settings_path = tmp_path / ".claude/settings.json"
    settings = json.loads(settings_path.read_text())
    unrelated = {
        "matcher": ".*",
        "hooks": [{"type": "command", "command": "echo keep"}],
    }
    settings["hooks"]["PermissionRequest"].append(unrelated)
    settings_path.write_text(json.dumps(settings))
    before = settings_path.read_text()
    with pytest.raises(FileExistsError):
        export_claude_code_package(
            tmp_path,
            zulip_config_file="/realm-b/user",
            zulip_bot_config_file="/realm-b/bot",
        )
    assert settings_path.read_text() == before
    export_claude_code_package(
        tmp_path,
        zulip_config_file="/realm-b/user",
        zulip_bot_config_file="/realm-b/bot",
        force=True,
    )
    after = settings_path.read_text()
    assert "/realm-a/" not in after
    assert "/realm-b/user" in after and "/realm-b/bot" in after
    settings = json.loads(after)
    assert unrelated in settings["hooks"]["PermissionRequest"]
    for groups in settings["hooks"].values():
        assert (
            sum(
                "zulipchat-mcp-hook" in hook.get("command", "")
                for group in groups
                for hook in group["hooks"]
            )
            == 1
        )
    export_claude_code_package(
        tmp_path,
        zulip_config_file="/realm-b/user",
        zulip_bot_config_file="/realm-b/bot",
        force=True,
    )
    assert settings_path.read_text() == after


def test_claude_reexport_rejects_ambiguous_hook_ownership_before_writing(tmp_path):
    export_claude_code_package(tmp_path, zulip_config_file="/realm-a/user")
    settings_path = tmp_path / ".claude/settings.json"
    settings = json.loads(settings_path.read_text())
    settings["hooks"]["PermissionRequest"][0]["hooks"][0]["command"] = (
        "env CUSTOM=1 uvx --from zulipchat-mcp zulipchat-mcp-hook "
        "--zulip-config-file /realm-a/user"
    )
    settings_path.write_text(json.dumps(settings))
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    with pytest.raises(ValueError, match="ownership"):
        export_claude_code_package(
            tmp_path, zulip_config_file="/realm-b/user", force=True
        )
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
