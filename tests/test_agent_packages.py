"""Validate real host formats and preserve user-owned export destinations."""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from zulipchat_mcp.core.tool_contract import READ_ONLY_TOOLS
from zulipchat_mcp.integrations.agent_package import (
    LAYOUTS,
    _parse,
    export_agent_package,
)
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
    if client == "pancode":
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
    assert len(list((tmp_path / skill_root).glob("*/SKILL.md"))) == 1


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


def test_pancode_export_preserves_other_servers_and_detects_duplicate_ids(tmp_path):
    destination = tmp_path / ".pancode/mcp.yaml"
    destination.parent.mkdir()
    destination.write_text(
        "version: 1\nservers:\n  - id: other\n    command: keep-me\n"
    )
    export_agent_package(
        tmp_path, client="pancode", zulip_config_file="/home/test/.zuliprc"
    )
    payload = yaml.safe_load(destination.read_text())
    assert payload["servers"][0] == {"id": "other", "command": "keep-me"}
    payload["servers"].append(payload["servers"][1])
    destination.write_text(yaml.safe_dump(payload))
    with pytest.raises(ValueError, match="Duplicate"):
        export_agent_package(
            tmp_path,
            client="pancode",
            zulip_config_file="/home/test/.zuliprc",
            force=True,
        )


@pytest.mark.parametrize("client", ["codex", "pancode", "opencode"])
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
        client="generic",
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
    assert len(list((tmp_path / "skills").glob("*/SKILL.md"))) == 1
    assert not (tmp_path / "hooks").exists()


@pytest.mark.parametrize("extended", [False, True])
def test_pancode_exports_classify_every_tool_from_its_annotations(tmp_path, extended):
    export_agent_package(
        tmp_path,
        client="pancode",
        zulip_config_file="/home/test/.zuliprc",
        extended_tools=extended,
    )
    export_agent_package(
        tmp_path / "plugin",
        client="pancode",
        mode="plugin",
        zulip_config_file="/home/test/.zuliprc",
        extended_tools=extended,
    )
    server = yaml.safe_load((tmp_path / ".pancode/mcp.yaml").read_text())["servers"][0]
    plugin = json.loads((tmp_path / "plugin/mcp.json").read_text())["mcpServers"][
        "zulipchat"
    ]
    classes = server["toolActionClasses"]
    assert plugin["toolActionClasses"] == classes
    assert plugin["timeoutMs"] == server["timeoutMs"] == 900000
    assert "actionClass" not in server
    from tests.tools.test_tool_tiers import EXTENDED_TOOL_COUNT
    from zulipchat_mcp.tools import CORE_TOOLS

    assert len(classes) == (EXTENDED_TOOL_COUNT if extended else len(CORE_TOOLS))
    assert {name for name, cls in classes.items() if cls == "read"} <= READ_ONLY_TOOLS
    assert classes["get_message"] == "read"
    assert classes["send_message"] == "execute"
    assert classes["edit_message"] == "destructive"
    if extended:
        assert classes["delete_draft"] == "destructive"
        # PanCode refuses a write path argument on a tool classed read.
        assert classes["download_file"] != "read"
        assert (
            server["toolPathArguments"]
            == plugin["toolPathArguments"]
            == {
                "download_file": {"download_path": "write"},
                "upload_file": {"file_path": "read"},
            }
        )
    else:
        assert "toolPathArguments" not in server


def test_server_ids_let_one_host_config_declare_several_organizations(tmp_path):
    for org in ("grc", "chronolog"):
        export_agent_package(
            tmp_path,
            client="pancode",
            zulip_config_file=f"/home/test/.zuliprc-{org}",
            server_id=f"zulipchat-{org}",
        )
    servers = yaml.safe_load((tmp_path / ".pancode/mcp.yaml").read_text())["servers"]
    assert [server["id"] for server in servers] == [
        "zulipchat-grc",
        "zulipchat-chronolog",
    ]
    assert servers[1]["args"][2] == "/home/test/.zuliprc-chronolog"

    export_agent_package(
        tmp_path,
        client="codex",
        zulip_config_file="/home/test/.zuliprc-grc",
        server_id="zulipchat-grc",
    )
    codex = _parse((tmp_path / ".codex/config.toml").read_text(), ".toml")
    assert list(codex["mcp_servers"]) == ["zulipchat-grc"]


@pytest.mark.parametrize("server_id", ["", "Zulip", "-grc", "a" * 33, "grc/../x"])
def test_invalid_server_ids_are_rejected_before_writing(tmp_path, server_id):
    with pytest.raises(ValueError, match="Server id"):
        export_agent_package(
            tmp_path,
            client="pancode",
            zulip_config_file="/home/test/.zuliprc",
            server_id=server_id,
        )
    assert not any(tmp_path.iterdir())


def test_checked_in_integration_skills_match_packaged_skills():
    import runpy

    script = Path(__file__).parents[1] / "scripts/sync_integration_templates.py"
    expected = runpy.run_path(str(script))["expected_templates"]()
    stale = [
        str(path) for path, content in expected.items() if path.read_text() != content
    ]
    assert (
        expected and not stale
    ), "Run scripts/sync_integration_templates.py to refresh: " + ", ".join(stale)


def test_read_only_pancode_export_runs_in_a_read_only_sandbox(tmp_path):
    export_agent_package(
        tmp_path,
        client="pancode",
        zulip_config_file="/home/test/.zuliprc",
        extended_tools=True,
        tool_profile="read-only",
    )
    server = yaml.safe_load((tmp_path / ".pancode/mcp.yaml").read_text())["servers"][0]
    assert server["args"][-3:] == ["--tool-profile", "read-only", "--ephemeral-state"]
    assert set(server["toolActionClasses"]) == READ_ONLY_TOOLS
    assert set(server["toolActionClasses"].values()) == {"read"}
    assert "toolPathArguments" not in server


def test_exports_pin_the_exporting_version_and_upgrade_only_with_force(tmp_path):
    from zulipchat_mcp import __version__

    export_agent_package(
        tmp_path / "generic",
        client="generic",
        zulip_config_file="/home/test/.zuliprc",
    )
    config_path, _, key = LAYOUTS["generic"]
    server = json.loads((tmp_path / "generic" / config_path).read_text())[key][
        "zulipchat"
    ]
    assert server["command"] == "uvx"
    assert server["args"][0] == f"zulipchat-mcp@{__version__}"

    claude = tmp_path / "claude"
    export_agent_package(
        claude, client="claude-code", zulip_config_file="/home/test/.zuliprc"
    )
    mcp = json.loads((claude / ".mcp.json").read_text())["mcpServers"]["zulipchat"]
    assert mcp["args"][0] == f"zulipchat-mcp@{__version__}"
    assert (claude / ".claude/skills/zulipchat/SKILL.md").is_file()


def test_merged_host_config_is_backed_up_and_keeps_its_mode(tmp_path):
    import os

    config_path, _, key = LAYOUTS["codex"]
    target = tmp_path / config_path
    target.parent.mkdir(parents=True)
    original = '# my own notes\n[mcp_servers.other]\ncommand = "other"\n'
    target.write_text(original)
    os.chmod(target, 0o640)
    previous = os.umask(0o022)
    try:
        results = export_agent_package(
            tmp_path, client="codex", zulip_config_file="/home/test/.zuliprc"
        )
    finally:
        os.umask(previous)
    (merged,) = [item for item in results if item["action"] == "merged"]
    assert Path(merged["backup"]).read_text() == original  # comments survive here
    assert os.stat(merged["backup"]).st_mode & 0o777 == 0o640
    assert os.stat(target).st_mode & 0o777 == 0o640
    assert "other" in target.read_text() and "zulipchat" in target.read_text()
    written = [item for item in results if item["action"] == "written"]
    assert written and all("backup" not in item for item in written)
    assert all(os.stat(item["path"]).st_mode & 0o777 == 0o644 for item in written)

    again = export_agent_package(
        tmp_path, client="codex", zulip_config_file="/home/test/.zuliprc"
    )
    assert {item["action"] for item in again} == {"unchanged"}
    assert len(list(target.parent.glob("*.bak-*"))) == 1


def test_checked_in_templates_pin_the_current_version():
    import re

    from zulipchat_mcp import __version__

    root = Path(__file__).parents[1] / "integrations"
    unpinned = re.compile(
        r"uvx zulipchat-mcp(?![@\w-])"
        r'|"zulipchat-mcp"\s*[,\]]|^\s*- zulipchat-mcp$'
        r"|uv run zulipchat-mcp",
        re.M,
    )
    pins = set()
    for path in root.rglob("*"):
        if not path.is_file() or "skills" in path.parts:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        assert not unpinned.search(text), f"{path} runs an unpinned zulipchat-mcp"
        pins.update(re.findall(r"zulipchat-mcp(?:@|==)([0-9][\w.]*)", text))
    # A version bump that misses the templates fails here.
    assert pins == {__version__}


def _integrate(monkeypatch, *args):
    import sys

    from zulipchat_mcp.integrations import registry

    monkeypatch.setattr(sys, "argv", ["zulipchat-mcp-integrate", *args])
    registry.main()


def test_pancode_print_is_a_user_scope_config_with_network(monkeypatch, capsys):
    from zulipchat_mcp import __version__
    from zulipchat_mcp.tools import CORE_TOOLS

    _integrate(
        monkeypatch,
        "print",
        "--client",
        "pancode",
        "--zulip-config-file",
        "/home/test/.zuliprc",
    )
    config = yaml.safe_load(capsys.readouterr().out)
    assert config["version"] == 1
    [server] = config["servers"]
    assert server["id"] == "zulipchat"
    assert server["command"] == "uvx"
    assert server["args"][0] == f"zulipchat-mcp@{__version__}"
    assert server["timeoutMs"] == 900000
    assert server["network"] is True
    assert set(server["toolActionClasses"]) == set(CORE_TOOLS)
    assert server["toolActionClasses"]["edit_message"] == "destructive"


def test_pancode_project_export_merges_and_refuses_another_entry(
    monkeypatch, capsys, tmp_path
):
    args = ["export", "--client", "pancode", "--output-dir", str(tmp_path)]
    _integrate(monkeypatch, *args, "--zulip-config-file", "/home/test/.zuliprc")
    config = yaml.safe_load((tmp_path / ".pancode/mcp.yaml").read_text())
    assert "network" not in config["servers"][0]
    assert (tmp_path / ".pancode/skills/zulipchat/SKILL.md").is_file()
    capsys.readouterr()

    _integrate(monkeypatch, *args, "--zulip-config-file", "/home/test/.zuliprc")
    again = {
        Path(item["path"]).name: item["action"]
        for item in json.loads(capsys.readouterr().out)["files"]
    }
    assert again == {"mcp.yaml": "merged", "SKILL.md": "unchanged"}
    assert yaml.safe_load((tmp_path / ".pancode/mcp.yaml").read_text()) == config
    with pytest.raises(SystemExit) as refused:
        _integrate(monkeypatch, *args, "--zulip-config-file", "/home/test/.other")
    assert refused.value.code != 0
    assert yaml.safe_load((tmp_path / ".pancode/mcp.yaml").read_text()) == config


def test_retired_client_name_is_rejected(monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as rejected:
        _integrate(
            monkeypatch,
            "export",
            "--client",
            "c" + "lio-coder",  # the removed client
            "--zulip-config-file",
            "/home/test/.zuliprc",
            "--output-dir",
            str(tmp_path),
        )
    assert rejected.value.code != 0
    assert not any(tmp_path.iterdir())


def test_pancode_pack_matches_the_exporter_and_validates(tmp_path):
    import runpy
    import shutil
    import subprocess
    import sys

    root = Path(__file__).parents[1]
    export_agent_package(
        tmp_path / "fresh",
        client="pancode",
        mode="plugin",
        tool_profile="full",
        zulip_config_file="~/.zuliprc",
    )
    fresh = {
        path.relative_to(tmp_path / "fresh").as_posix(): path.read_bytes()
        for path in (tmp_path / "fresh").rglob("*")
        if path.is_file()
    }
    pack = {
        path.relative_to(root / "pancode").as_posix(): path.read_bytes()
        for path in (root / "pancode").rglob("*")
        if path.is_file()
    }
    assert pack == fresh
    manifest = json.loads(pack["plugin.json"])
    assert manifest["extensions"]["dev.pancode"] == {
        "manifestVersion": 1,
        "compatibility": {"pancode": ">=0.9.0"},
    }
    schema = Path(__file__).parent / "fixtures/agent-plugins-1.0.0/plugin.schema.json"
    jsonschema.Draft202012Validator(json.loads(schema.read_text())).validate(manifest)

    script = root / "scripts/sync_integration_templates.py"
    assert runpy.run_path(str(script))["pack_problems"](root / "pancode") == []
    stale = tmp_path / "stale"
    shutil.copytree(root / "pancode", stale)
    (stale / "mcp.json").write_text("{}\n")
    checked = subprocess.run(
        [sys.executable, str(script), "--check", "--pack-dir", str(stale)],
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 1
    assert f"stale: {stale / 'mcp.json'}" in checked.stdout
