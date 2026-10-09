"""Portable Agent Plugins and native coding-agent configuration exports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import tomli_w
import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .. import __version__
from ..skill_content import skill_files
from .package_writer import write_package

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

# Antigravity CLI uses a user-scoped MCP file; its export is a staging fragment.
# Project skills can be installed independently.
LAYOUTS = {
    "codex": (".codex/config.toml", ".agents/skills", "mcp_servers"),
    "opencode": ("opencode.json", ".opencode/skills", "mcp"),
    "copilot": (".mcp.json", ".github/skills", "mcpServers"),
    "vscode": (".vscode/mcp.json", ".github/skills", "servers"),
    "antigravity-cli": ("mcp_config.json", ".agents/skills", "mcpServers"),
    "clio-coder": (".clio-coder/mcp.yaml", ".clio-coder/skills", "servers"),
    "generic": (".mcp.json", ".agents/skills", "mcpServers"),
}


def portable_plugin_files(
    base: dict[str, Any], server_id: str = "zulipchat"
) -> dict[str, str]:
    """Render Agent Plugins 1.0.0 without imposing host-specific permissions."""
    manifest = {
        "$schema": PLUGIN_SCHEMA,
        "name": "zulipchat",
        "version": __version__,
        "description": "Zulip messaging, search, and topic-bound agent collaboration.",
        "author": {"name": "Anthony Kougkas"},
        "homepage": "https://github.com/akougkas/zulipchat-mcp",
        "repository": "https://github.com/akougkas/zulipchat-mcp",
        "license": "MIT",
        "keywords": ["zulip", "mcp", "chatops", "agent-skills"],
    }
    mcp = {
        "$schema": MCP_SCHEMA,
        "mcpServers": {server_id: {"type": "stdio", **base}},
    }
    return {
        "plugin.json": json.dumps(manifest, indent=2) + "\n",
        "mcp.json": json.dumps(mcp, indent=2) + "\n",
        **{
            f"skills/{relative}": content for relative, content in skill_files().items()
        },
    }


def _parse(content: str, suffix: str) -> dict[str, Any]:
    if suffix == ".toml":
        payload = tomllib.loads(content)
    elif suffix == ".yaml":
        payload = yaml.safe_load(content)
    else:
        payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("Existing client configuration must contain an object")
    return payload


def _serialize(payload: dict[str, Any], suffix: str) -> str:
    if suffix == ".toml":
        return tomli_w.dumps(payload)
    if suffix == ".yaml":
        return yaml.safe_dump(payload, sort_keys=False)
    return json.dumps(payload, indent=2) + "\n"


def _merge_config(
    current: str,
    incoming: str,
    *,
    path: str,
    key: str,
    force: bool,
    server_id: str = "zulipchat",
) -> str:
    suffix = Path(path).suffix
    existing = _parse(current, suffix)
    new = _parse(incoming, suffix)
    if suffix == ".yaml":
        if existing.get("version") != 1 or set(existing) - {"version", "servers"}:
            raise ValueError("Clio MCP configuration must use the version 1 schema")
        servers = existing.setdefault("servers", [])
        if not isinstance(servers, list) or any(
            not isinstance(server, dict) for server in servers
        ):
            raise ValueError("Clio MCP servers must be an array of objects")
        matches = [
            index
            for index, server in enumerate(servers)
            if server.get("id") == server_id
        ]
        if len(matches) > 1:
            raise ValueError(f"Duplicate {server_id} server declarations")
        replacement = new["servers"][0]
        if matches:
            if servers[matches[0]] != replacement and not force:
                raise FileExistsError(
                    f"Existing {server_id} declaration differs; use --force to replace it"
                )
            servers[matches[0]] = replacement
        else:
            servers.append(replacement)
    else:
        servers = existing.setdefault(key, {})
        if not isinstance(servers, dict):
            raise ValueError(f"Client configuration {key} must be an object")
        replacement = new[key][server_id]
        if server_id in servers and servers[server_id] != replacement and not force:
            raise FileExistsError(
                f"Existing {server_id} declaration differs; use --force to replace it"
            )
        servers[server_id] = replacement
    return _serialize(existing, suffix)


def export_agent_package(
    output_dir: str | Path,
    *,
    client: str,
    zulip_config_file: str,
    zulip_bot_config_file: str | None = None,
    mode: str = "standalone",
    extended_tools: bool = False,
    force: bool = False,
    server_id: str = "zulipchat",
) -> list[dict[str, str]]:
    """Export host assets; never install, trust, or launch a coding agent."""
    from .registry import _build_base_config, _render_for_client, validate_server_id

    validate_server_id(server_id)

    base = _build_base_config(zulip_config_file, zulip_bot_config_file, extended_tools)
    if mode == "plugin":
        return write_package(
            output_dir, portable_plugin_files(base, server_id), force=force
        )
    if mode != "standalone" or client not in LAYOUTS:
        raise ValueError(f"Unsupported standalone export client/mode: {client}/{mode}")
    config_path, skill_root, key = LAYOUTS[client]
    if client == "opencode" and (Path(output_dir) / "opencode.jsonc").exists():
        raise ValueError(
            "Existing opencode.jsonc: merge a printed snippet manually instead of creating a competing opencode.json"
        )
    documents = {
        config_path: _render_for_client(client, base, server_id) + "\n",
        **{
            f"{skill_root}/{relative}": content
            for relative, content in skill_files().items()
        },
    }

    def merge(current: str, incoming: str) -> str:
        return _merge_config(
            current,
            incoming,
            path=config_path,
            key=key,
            force=force,
            server_id=server_id,
        )

    return write_package(
        output_dir, documents, force=force, mergers={config_path: merge}
    )
