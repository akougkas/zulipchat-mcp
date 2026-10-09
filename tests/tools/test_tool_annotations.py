"""Real-registration contract for MCP tool annotations."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp_tasks import TasksExtension

from zulipchat_mcp.core.tool_contract import READ_ONLY_TOOLS, ToolContractMiddleware
from zulipchat_mcp.tools import register_core_tools, register_extended_tools
from zulipchat_mcp.tools.registration import tool_annotations

HINTS = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}

# Tools that can delete or irreversibly overwrite user-visible data.
DESTRUCTIVE = {
    "edit_message",
    "edit_draft",
    "delete_draft",
    "manage_scheduled_message",
    "manage_files",
    "agents_channel_topic_ops",
}

# Tools that never reach Zulip (local state or pure computation).
LOCAL_ONLY = {
    "server_info",
    "switch_identity",
    "ensure_agent_session",
    "send_agent_status",
    "manage_task",
    "list_sessions",
    "list_instances",
    "list_command_types",
    "construct_narrow",
}

# Non-read-only tools where repeating the same call has no further effect.
IDEMPOTENT_WRITES = {
    "edit_message",
    "add_reaction",
    "toggle_reaction",
    "update_status",
    "manage_user_mute",
    "manage_message_flags",
    "update_message_flags_for_narrow",
    "register_agent",
    "ensure_agent_session",
    "switch_identity",
    "wait_for_response",
    "get_events",
    "deregister_events",
    "edit_draft",
    "delete_draft",
    "get_drafts",
    "get_daily_summary",
    "analyze_stream_with_llm",
    "analyze_team_activity_with_llm",
    "intelligent_report_generator",
}


def _server(*, extended: bool, read_only: bool) -> FastMCP[Any]:
    mcp = FastMCP("annotation-contract", tasks=False)
    mcp.add_extension(TasksExtension())
    mcp.add_middleware(ToolContractMiddleware(read_only=read_only))
    register_core_tools(mcp)
    if extended:
        register_extended_tools(mcp)
    return mcp


async def _annotations(
    *, extended: bool, read_only: bool, mode: str
) -> dict[str, dict[str, Any]]:
    async with Client(
        _server(extended=extended, read_only=read_only), mode=mode
    ) as client:
        tools = await client.list_tools()
    wire: dict[str, dict[str, Any]] = {}
    for tool in tools:
        assert tool.title, f"{tool.name} has no title"
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        data = tool.annotations.model_dump(by_alias=True, exclude_none=True)
        assert data.get("title") == tool.title
        wire[tool.name] = data
    return wire


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
@pytest.mark.parametrize(("extended", "count"), [(False, 20), (True, 60)])
async def test_every_tool_advertises_complete_annotations(mode, extended, count):
    wire = await _annotations(extended=extended, read_only=False, mode=mode)
    assert len(wire) == count
    for name, data in wire.items():
        assert HINTS <= data.keys(), f"{name} is missing hints: {HINTS - data.keys()}"
        assert all(isinstance(data[hint], bool) for hint in HINTS)


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
@pytest.mark.parametrize(("extended", "count"), [(False, 9), (True, 23)])
async def test_read_only_hint_is_exactly_the_read_only_profile(mode, extended, count):
    full = await _annotations(extended=extended, read_only=False, mode=mode)
    read_only_hinted = {n for n, d in full.items() if d["readOnlyHint"]}
    assert len(read_only_hinted) == count
    assert read_only_hinted == set(full) & READ_ONLY_TOOLS

    profile = await _annotations(extended=extended, read_only=True, mode=mode)
    assert set(profile) == read_only_hinted
    for name, data in profile.items():
        assert data["readOnlyHint"] is True, name
        assert data["destructiveHint"] is False, name
        assert data["idempotentHint"] is True, name


async def test_extended_tier_covers_the_whole_read_only_policy_set():
    wire = await _annotations(extended=True, read_only=False, mode="legacy")
    assert READ_ONLY_TOOLS == {n for n, d in wire.items() if d["readOnlyHint"]}


async def test_write_tool_classification():
    wire = await _annotations(extended=True, read_only=False, mode="legacy")
    writes = {n: d for n, d in wire.items() if not d["readOnlyHint"]}

    assert {n for n, d in writes.items() if d["destructiveHint"]} == DESTRUCTIVE
    assert {n for n, d in wire.items() if not d["openWorldHint"]} == LOCAL_ONLY
    assert {n for n, d in writes.items() if d["idempotentHint"]} == IDEMPOTENT_WRITES
    for name in (
        "send_message",
        "teleport_chat",
        "agent_message",
        "cross_post_message",
    ):
        assert writes[name]["idempotentHint"] is False, name
        assert writes[name]["destructiveHint"] is False, name


def test_read_only_tool_cannot_be_declared_destructive():
    with pytest.raises(ValueError, match="read-only"):
        tool_annotations("get_message", "Get message", destructive=True)
    assert tool_annotations("get_message", "Get message").read_only_hint is True
    assert tool_annotations("send_message", "Send message").read_only_hint is False
