"""FastMCP task registration contract tests."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from fastmcp.utilities.tasks import TASKS_EXTENSION_ID
from fastmcp_tasks import TasksExtension

from zulipchat_mcp.tools import register_core_tools, register_extended_tools


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
