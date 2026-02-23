"""CLI helper for generating MCP client configuration snippets.

This module powers the `zulipchat-mcp-integrate` entrypoint.
It prints copy/paste snippets for common MCP clients.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from .. import __version__

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


def _render_for_client(client: str, base: dict[str, Any]) -> str:
    if client == "claude-code":
        return "claude mcp add zulipchat -- " + " ".join(
            [base["command"], *[str(arg) for arg in base["args"]]]
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
        rendered_args = ", ".join(f'"{arg}"' for arg in base["args"])
        return (
            "[mcp_servers.zulipchat]\n"
            f'command = "{base["command"]}"\n'
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
    print_parser.add_argument("--zulip-config-file", required=True)
    print_parser.add_argument("--zulip-bot-config-file")
    print_parser.add_argument("--extended-tools", action="store_true")

    args = parser.parse_args()

    if args.command == "list":
        print("\n".join(CLIENTS))
        return

    if args.command == "print":
        base = _build_base_config(
            args.zulip_config_file,
            args.zulip_bot_config_file,
            args.extended_tools,
        )
        print(_render_for_client(args.client, base))


if __name__ == "__main__":
    main()
