"""CLI helper for generating MCP client configuration snippets.

This module powers the `zulipchat-mcp-integrate` entrypoint.
It prints copy/paste snippets for common MCP clients.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
from pathlib import Path
from typing import Any

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


def _render_for_client(client: str, base: dict[str, Any]) -> str:
    if client == "claude-code":
        return shlex.join(
            [
                "claude",
                "mcp",
                "add",
                "zulipchat",
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
        "generic",
    }:
        return json.dumps({"mcpServers": {"zulipchat": base}}, indent=2)

    if client == "vscode":
        payload = {
            "servers": {
                "zulipchat": {
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
                "zulipchat": {
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
            "[mcp_servers.zulipchat]\n"
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
    export_parser.add_argument("--client", choices=["claude-code"], required=True)
    export_parser.add_argument("--output-dir", required=True)
    export_parser.add_argument("--zulip-config-file", required=True)
    export_parser.add_argument("--zulip-bot-config-file")
    export_parser.add_argument(
        "--mode",
        choices=["standalone", "plugin"],
        default="standalone",
    )
    export_parser.add_argument("--extended-tools", action="store_true")
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
        print(_render_for_client(args.client, base))
        return

    if args.command == "export":
        if args.client != "claude-code":
            raise ValueError(f"Unsupported export client: {args.client}")
        results = export_claude_code_package(
            Path(args.output_dir),
            zulip_config_file=args.zulip_config_file,
            zulip_bot_config_file=args.zulip_bot_config_file,
            mode=args.mode,
            extended_tools=args.extended_tools,
            force=args.force,
        )
        print(json.dumps({"status": "success", "files": results}, indent=2))


if __name__ == "__main__":
    main()
