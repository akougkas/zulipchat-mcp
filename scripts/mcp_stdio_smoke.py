#!/usr/bin/env python3
"""Smoke-test the MCP stdio server without contacting a real Zulip server."""

from __future__ import annotations

import argparse
import asyncio
import os
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
        for name in ("UV_PROJECT_ENVIRONMENT", "UV_CACHE_DIR"):
            if name in os.environ:
                env[name] = os.environ[name]
        for mode in ("legacy", "2026-07-28"):
            for extended in (False, True):
                for read_only in (False, True):
                    args = [*command, *(["--extended-tools"] if extended else [])]
                    if read_only:
                        args += ["--tool-profile", "read-only"]
                    await _smoke_connection(
                        args, expected_version, mode, extended, read_only, env
                    )


async def _smoke_connection(
    command: list[str],
    expected_version: str,
    mode: str,
    extended: bool,
    read_only: bool,
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
        required = (
            REQUIRED_TOOLS - {"send_message", "teleport_chat"}
            if read_only
            else REQUIRED_TOOLS
        )
        missing = sorted(required - names)
        if missing:
            raise AssertionError(f"Missing required tools: {missing}")
        expected_count = (
            (23 if extended else 9) if read_only else (60 if extended else 20)
        )
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
        capabilities = data["capabilities"]
        if capabilities["enabled_tools"] != sorted(names):
            raise AssertionError("server_info capabilities disagree with discovery")
        if capabilities["enabled_tool_count"] != len(tools):
            raise AssertionError("server_info tool count disagrees with discovery")
        if read_only:
            denied = await client.call_tool("send_message", {}, raise_on_error=False)
            if (
                not denied.is_error
                or denied.structured_content.get("error_code") != "POLICY_DENIED"
            ):
                raise AssertionError("Read-only direct execution was not denied")
            if denied.structured_content.get("retryable") is not False:
                raise AssertionError("Policy denial must prohibit unchanged retries")

        resources = await client.list_resources()
        if len(resources) != 4:
            raise AssertionError(
                f"Expected four packaged skills, got {len(resources)} resources"
            )
        for resource in resources:
            content = await client.read_resource(str(resource.uri))
            if not content or "name: zulipchat" not in content[0].text:
                raise AssertionError(f"Invalid packaged skill: {resource.uri}")

        print(
            f"ok: {mode}, {capabilities['tool_profile']}, {len(tools)} tools, "
            f"four skills, server_info v{data['version']}"
        )


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
