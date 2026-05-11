"""FastMCP task registration contract tests."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from zulipchat_mcp.tools import register_core_tools, register_extended_tools


@pytest.mark.asyncio
async def test_task_support_is_opt_in_for_long_running_tools() -> None:
    """Only explicitly selected async tools should advertise MCP task support."""
    mcp = FastMCP("task-contract", tasks=False)
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
    register_core_tools(mcp)
    register_extended_tools(mcp)
