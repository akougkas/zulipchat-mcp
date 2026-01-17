"""Exercise tool registration functions to cover registration code paths."""

from __future__ import annotations


def _dummy_tool_decorator(name: str | None = None, description: str | None = None):
    def _wrap(fn):
        return fn

    return _wrap


class DummyMCP:
    def tool(self, name: str | None = None, description: str | None = None):
        return _dummy_tool_decorator(name, description)


def test_register_all_tools():
    """Test that all tool registration functions work without errors."""
    from zulipchat_mcp.tools import (
        register_ai_analytics_tools,
        register_emoji_messaging_tools,
        register_event_management_tools,
        register_events_tools,
        register_files_tools,
        register_mark_messaging_tools,
        register_messaging_tools,
        register_schedule_messaging_tools,
        register_search_tools,
        register_stream_management_tools,
        register_system_tools,
        register_topic_management_tools,
        register_users_tools,
    )

    mcp = DummyMCP()
    register_messaging_tools(mcp)
    register_schedule_messaging_tools(mcp)
    register_emoji_messaging_tools(mcp)
    register_mark_messaging_tools(mcp)
    register_search_tools(mcp)
    register_stream_management_tools(mcp)
    register_topic_management_tools(mcp)
    register_event_management_tools(mcp)
    register_events_tools(mcp)
    register_ai_analytics_tools(mcp)
    register_users_tools(mcp)
    register_files_tools(mcp)
    register_system_tools(mcp)
