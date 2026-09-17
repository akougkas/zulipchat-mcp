#!/usr/bin/env python3
"""Smoke-test the MCP stdio server without contacting a real Zulip server."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]

FAKE_ENV = {
    "ZULIP_EMAIL": "test@example.com",
    "ZULIP_API_KEY": "test-key",
    "ZULIP_SITE": "http://127.0.0.1:9",
    "ZULIP_BOT_EMAIL": "bot@example.com",
    "ZULIP_BOT_API_KEY": "bot-key",
}

REQUIRED_TOOLS = {
    "send_message",
    "search_messages",
    "server_info",
    "teleport_chat",
}


async def _smoke(command: list[str], expected_version: str) -> None:
    with TemporaryDirectory(prefix="zulipchat-stdio-") as scratch:
        config_file = Path(scratch) / "zuliprc"
        config_file.write_text(
            "[api]\nemail=test@example.com\nkey=test-key\nsite=http://127.0.0.1:9\n"
        )
        env = {
            **FAKE_ENV,
            "ZULIP_CONFIG_FILE": str(config_file),
            "ZULIP_BOT_CONFIG_FILE": str(config_file),
            "ZULIPCHAT_DB_PATH": str(Path(scratch) / "smoke.duckdb"),
            "ZULIPCHAT_EXTENDED_TOOLS": "0",
            "ANTHROPIC_API_KEY": "",
        }
        for mode in ("legacy", "2026-07-28"):
            for extended in (False, True):
                args = [*command, *(["--extended-tools"] if extended else [])]
                await _smoke_connection(args, expected_version, mode, extended, env)


async def _smoke_connection(
    command: list[str],
    expected_version: str,
    mode: str,
    extended: bool,
    env: dict[str, str],
) -> None:
    transport = StdioTransport(
        command=command[0],
        args=command[1:],
        cwd=str(ROOT),
        env=env,
    )
    async with Client(transport, mode=mode, init_timeout=60, timeout=20) as client:
        # Modern MCP uses discovery and request envelopes; ping is legacy-only.
        if mode == "legacy" and not await client.ping():
            raise AssertionError("MCP ping failed")

        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        missing = sorted(REQUIRED_TOOLS - names)
        if missing:
            raise AssertionError(f"Missing required tools: {missing}")
        expected_count = 60 if extended else 20
        if len(tools) != expected_count:
            raise AssertionError(f"Expected {expected_count} tools, got {len(tools)}")

        result = await client.call_tool("server_info", {})
        data = result.data
        if data["status"] != "success":
            raise AssertionError(f"server_info returned {data['status']!r}")
        if data["version"] != expected_version:
            raise AssertionError(
                f"server_info version mismatch: "
                f"expected {expected_version}, got {data['version']}"
            )

        print(f"ok: {mode}, {len(tools)} tools, server_info v{data['version']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start an MCP stdio server with fake credentials and call server_info."
    )
    parser.add_argument("--expected-version", required=True)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run after --, for example: -- uv run zulipchat-mcp",
    )
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("missing command after --")

    asyncio.run(_smoke(command, args.expected_version))


if __name__ == "__main__":
    main()
