"""CLI helper for generating MCP client configuration snippets.

This module powers the `zulipchat-mcp-integrate` entrypoint.
It prints copy/paste snippets for common MCP clients.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

import yaml

from .. import __version__
from .claude_code_package import export_claude_code_package

CLIENTS = [
    "claude-code",
    "claude-desktop",
    "gemini",
    "codex",
    "cursor",
    "windsurf",
    "vscode",
    "opencode",
    "antigravity",
    "antigravity-cli",
    "copilot",
    "clio-coder",
    "generic",
]


def _build_base_config(
    zulip_config_file: str,
    zulip_bot_config_file: str | None,
    extended_tools: bool,
) -> dict[str, Any]:
    args = ["zulipchat-mcp", "--zulip-config-file", zulip_config_file]
    if zulip_bot_config_file:
        args.extend(["--zulip-bot-config-file", zulip_bot_config_file])
    if extended_tools:
        args.append("--extended-tools")

    return {
        "command": "uvx",
        "args": args,
    }


def _render_remote_for_client(client: str, url: str, token: str | None) -> str:
    """Render a snippet pointing a client at a remote HTTP server."""
    headers = {"Authorization": f"Bearer {token}"} if token else None

    if client == "claude-code":
        args = ["claude", "mcp", "add", "--transport", "http", "zulipchat", url]
        if token:
            args.extend(["--header", f"Authorization: Bearer {token}"])
        return shlex.join(args)

    if client == "generic":
        payload: dict[str, Any] = {"zulipchat": {"type": "http", "url": url}}
        if headers:
            payload["zulipchat"]["headers"] = headers
        return json.dumps({"mcpServers": payload}, indent=2)

    if client == "vscode":
        server: dict[str, Any] = {"type": "http", "url": url}
        if headers:
            server["headers"] = headers
        return json.dumps({"servers": {"zulipchat": server}}, indent=2)

    raise ValueError(
        f"Remote HTTP snippets are supported for: claude-code, vscode, generic. "
        f"Got: {client}"
    )


SERVER_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


def validate_server_id(server_id: str) -> str:
    """Accept ids every supported host can use as a server key."""
    if not SERVER_ID_PATTERN.fullmatch(server_id):
        raise ValueError(
            "Server id must be 1-32 lowercase letters, digits, '-' or '_', "
            "starting with a letter or digit"
        )
    return server_id


def _render_for_client(
    client: str, base: dict[str, Any], server_id: str = "zulipchat"
) -> str:
    if client == "claude-code":
        return shlex.join(
            [
                "claude",
                "mcp",
                "add",
                server_id,
                "--",
                base["command"],
                *[str(arg) for arg in base["args"]],
            ]
        )

    if client in {
        "claude-desktop",
        "gemini",
        "cursor",
        "windsurf",
        "antigravity",
        "antigravity-cli",
        "generic",
    }:
        return json.dumps({"mcpServers": {server_id: base}}, indent=2)

    if client == "copilot":
        return json.dumps(
            {"mcpServers": {server_id: {"type": "local", **base, "tools": ["*"]}}},
            indent=2,
        )

    if client == "clio-coder":
        return yaml.safe_dump(
            {
                "version": 1,
                "servers": [{"id": server_id, **base, "timeoutMs": 900000}],
            },
            sort_keys=False,
        )

    if client == "vscode":
        payload = {
            "servers": {
                server_id: {
                    "type": "stdio",
                    "command": base["command"],
                    "args": base["args"],
                }
            }
        }
        return json.dumps(payload, indent=2)

    if client == "opencode":
        payload = {
            "mcp": {
                server_id: {
                    "type": "local",
                    "enabled": True,
                    "command": [base["command"], *base["args"]],
                }
            }
        }
        return json.dumps(payload, indent=2)

    if client == "codex":
        rendered_args = ", ".join(
            json.dumps(str(arg), ensure_ascii=False) for arg in base["args"]
        )
        return (
            f"[mcp_servers.{server_id}]\n"
            f'command = {json.dumps(base["command"], ensure_ascii=False)}\n'
            f"args = [{rendered_args}]"
        )

    raise ValueError(f"Unsupported client: {client}")


def main() -> None:
    """Entrypoint for integration snippet generation."""
    parser = argparse.ArgumentParser(
        description="Generate ZulipChat MCP integration snippets for MCP clients."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List supported client targets")

    print_parser = sub.add_parser("print", help="Print integration snippet")
    print_parser.add_argument("--client", choices=CLIENTS, required=True)
    print_parser.add_argument(
        "--zulip-config-file",
        help="Required for local stdio snippets (not used with --remote-url)",
    )
    print_parser.add_argument("--zulip-bot-config-file")
    print_parser.add_argument("--extended-tools", action="store_true")
    print_parser.add_argument(
        "--server-id",
        default="zulipchat",
        help=(
            "MCP server name in the host configuration (default: zulipchat). "
            "Use one id per Zulip organization, e.g. zulipchat-grc."
        ),
    )
    print_parser.add_argument(
        "--remote-url",
        help=(
            "Point the client at a remote ZulipChat server instead of a local "
            "stdio process (e.g. http://mcp.internal:8000/mcp). Requires the "
            "server to run with --transport http."
        ),
    )
    print_parser.add_argument(
        "--remote-token",
        default=os.environ.get("ZULIPCHAT_HTTP_AUTH_TOKEN"),
        help="Bearer token for --remote-url (default: ZULIPCHAT_HTTP_AUTH_TOKEN)",
    )

    export_parser = sub.add_parser(
        "export",
        help="Export richer client integration assets",
    )
    export_parser.add_argument(
        "--client",
        choices=[
            "claude-code",
            "codex",
            "opencode",
            "copilot",
            "vscode",
            "antigravity-cli",
            "clio-coder",
            "generic",
        ],
        required=True,
    )
    export_parser.add_argument("--output-dir", required=True)
    export_parser.add_argument("--zulip-config-file", required=True)
    export_parser.add_argument("--zulip-bot-config-file")
    export_parser.add_argument(
        "--mode",
        choices=["standalone", "plugin"],
        default="standalone",
    )
    export_parser.add_argument("--extended-tools", action="store_true")
    export_parser.add_argument(
        "--server-id",
        default="zulipchat",
        help=(
            "MCP server name in the host configuration (default: zulipchat). "
            "Use one id per Zulip organization, e.g. zulipchat-grc."
        ),
    )
    export_parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    if args.command == "list":
        print("\n".join(CLIENTS))
        return

    if args.command == "print":
        if args.remote_url:
            try:
                snippet = _render_remote_for_client(
                    args.client, args.remote_url, args.remote_token
                )
            except ValueError as e:
                print_parser.error(str(e))
            print(snippet)
            return
        if not args.zulip_config_file:
            print_parser.error(
                "--zulip-config-file is required unless --remote-url is given"
            )
        base = _build_base_config(
            args.zulip_config_file,
            args.zulip_bot_config_file,
            args.extended_tools,
        )
        try:
            server_id = validate_server_id(args.server_id)
        except ValueError as e:
            print_parser.error(str(e))
        print(_render_for_client(args.client, base, server_id))
        return

    if args.command == "export":
        from .agent_package import export_agent_package

        exporter = (
            export_claude_code_package
            if args.client == "claude-code"
            else export_agent_package
        )
        options: dict[str, str] = (
            {} if args.client == "claude-code" else {"client": args.client}
        )
        if args.server_id != "zulipchat":
            if args.client == "claude-code":
                export_parser.error(
                    "--server-id is not supported for claude-code exports; "
                    "its hooks bind one account per project"
                )
            options["server_id"] = args.server_id
        try:
            results = exporter(
                Path(args.output_dir),
                zulip_config_file=args.zulip_config_file,
                zulip_bot_config_file=args.zulip_bot_config_file,
                mode=args.mode,
                extended_tools=args.extended_tools,
                force=args.force,
                **options,
            )
        except (ValueError, OSError) as error:
            export_parser.error(str(error))
        print(json.dumps({"status": "success", "files": results}, indent=2))


if __name__ == "__main__":
    main()
