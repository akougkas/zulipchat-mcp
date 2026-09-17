"""FastMCP task registration contract tests."""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.utilities.tasks import TASKS_EXTENSION_ID
from fastmcp_tasks import TasksExtension, call_tool_task

from zulipchat_mcp.tools import register_core_tools, register_extended_tools


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_task_enabled_wait_tool_completes_with_real_protocol(mode, monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from zulipchat_mcp.tools import agents

    coordinator = MagicMock()
    coordinator.wait_for_request_async = AsyncMock(
        return_value={
            "status": "success",
            "request_status": "answered",
            "response": "approve",
        }
    )
    monkeypatch.setattr(agents, "ensure_listener", lambda: None)
    monkeypatch.setattr(agents, "_get_coordinator", lambda: coordinator)
    mcp = FastMCP("task-execution-contract", tasks=False)
    mcp.add_extension(TasksExtension())
    register_core_tools(mcp)
    async with Client(mcp, mode=mode, timeout=10) as client:
        if mode == "legacy":
            assert await client.ping()
            result = await client.call_tool(
                "wait_for_response", {"request_id": "request-1"}
            )
        else:
            task = await call_tool_task(
                client, "wait_for_response", {"request_id": "request-1"}
            )
            result = await task.result()
        assert result.data["response"] == "approve"
    coordinator.wait_for_request_async.assert_awaited_once_with(
        "request-1", timeout_seconds=300
    )


@pytest.mark.asyncio
async def test_task_support_is_opt_in_for_long_running_tools() -> None:
    """Only explicitly selected async tools should advertise MCP task support."""
    mcp = FastMCP("task-contract", tasks=False)
    mcp.add_extension(TasksExtension())
    register_core_tools(mcp)
    register_extended_tools(mcp)

    tools = {tool.name: tool for tool in await mcp.list_tools()}
    task_tools = {
        name for name, tool in tools.items() if tool.task_config.supports_tasks()
    }

    assert task_tools == {"listen_events", "teleport_chat", "wait_for_response"}
    assert tools["teleport_chat"].task_config.mode == "optional"
    assert tools["wait_for_response"].task_config.mode == "optional"
    assert tools["listen_events"].task_config.mode == "optional"


def test_core_and_extended_register_with_real_fastmcp() -> None:
    """Real FastMCP registration catches task/dependency/signature regressions."""
    mcp = FastMCP("registration-contract", tasks=False)
    mcp.add_extension(TasksExtension())
    register_core_tools(mcp)
    register_extended_tools(mcp)


def test_server_registers_tasks_extension() -> None:
    """server.py must wire the SEP-2663 extension FastMCP 4 requires for task= tools."""
    import zulipchat_mcp.server as server_mod

    mcp = FastMCP("extension-contract", tasks=False)
    mcp.add_extension(TasksExtension())

    extensions = getattr(mcp, "_extensions", {})
    assert TASKS_EXTENSION_ID in extensions
    # Guard against the import disappearing from server.py (removed kwargs or
    # a future refactor could silently drop task support for long-running tools).
    assert server_mod.TasksExtension is TasksExtension
