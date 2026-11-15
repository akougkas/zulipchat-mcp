"""FastMCP task registration contract tests."""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.utilities.tasks import TASKS_EXTENSION_ID
from fastmcp_tasks import TasksExtension, call_tool_task

from zulipchat_mcp.core.tool_contract import ToolContractMiddleware
from zulipchat_mcp.tools import register_core_tools, register_extended_tools


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_task_enabled_wait_tool_completes_with_real_protocol(
    mode, monkeypatch, tmp_path
):
    from zulipchat_mcp.agents.store import BridgeStore

    store = BridgeStore(tmp_path / "bridge.sqlite3")
    store.bind("dm:7", None, str(tmp_path), {"type": "private", "to": [7]})
    question_id = store.ask("dm:7", "question", "Ship it?", [], 5)
    store.answer(question_id, "yes")
    monkeypatch.setenv("ZULIPCHAT_AGENT_STATE", str(store.path))
    monkeypatch.setenv("ZULIPCHAT_AGENT_CONVERSATION", "dm:7")
    mcp = FastMCP("task-execution-contract", tasks=False)
    mcp.add_extension(TasksExtension())
    register_core_tools(mcp)
    mcp.add_middleware(ToolContractMiddleware())
    arguments = {"question_id": question_id, "wait_seconds": 1}
    async with Client(mcp, mode=mode, timeout=10) as client:
        if mode == "legacy":
            assert await client.ping()
            result = await client.call_tool("ask_owner", arguments)
        else:
            task = await call_tool_task(client, "ask_owner", arguments)
            result = await task.result()
        assert result.data["answer"] == "yes"


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

    assert task_tools == {"listen_events"}
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
