#!/usr/bin/env python3
"""Smoke-test the MCP stdio server without contacting a real Zulip server."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]

FAKE_ENV = {
    "ZULIP_EMAIL": "test@example.com",
    "ZULIP_API_KEY": "test-key",
    "ZULIP_SITE": "https://example.zulipchat.com",
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
    transport = StdioTransport(
        command=command[0],
        args=command[1:],
        cwd=str(ROOT),
        env=FAKE_ENV,
    )
    async with Client(transport, init_timeout=60, timeout=20) as client:
        if not await client.ping():
            raise AssertionError("MCP ping failed")

        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        missing = sorted(REQUIRED_TOOLS - names)
        if missing:
            raise AssertionError(f"Missing required tools: {missing}")

        result = await client.call_tool("server_info", {})
        data = result.data
        if data["status"] != "success":
            raise AssertionError(f"server_info returned {data['status']!r}")
        if data["version"] != expected_version:
            raise AssertionError(
                f"server_info version mismatch: "
                f"expected {expected_version}, got {data['version']}"
            )

        print(f"ok: {len(tools)} tools, server_info v{data['version']}")


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
