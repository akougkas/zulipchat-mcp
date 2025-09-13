"""Exercise tool registration functions to cover registration code paths."""

from __future__ import annotations


def _dummy_tool_decorator(description: str):
    def _wrap(fn):
        return fn

    return _wrap


class DummyMCP:
    def tool(self, description: str | None = None):
        return _dummy_tool_decorator(description or "")


def test_register_messaging_and_search_and_streams_and_users_tools():
    from zulipchat_mcp.tools.admin_v25 import register_admin_v25_tools
    from zulipchat_mcp.tools.events_v25 import register_events_v25_tools
    from zulipchat_mcp.tools.files_v25 import register_files_v25_tools
    from zulipchat_mcp.tools.messaging_v25 import register_messaging_v25_tools
    from zulipchat_mcp.tools.search_v25 import register_search_v25_tools
    from zulipchat_mcp.tools.streams_v25 import register_streams_v25_tools
    from zulipchat_mcp.tools.users_v25 import register_users_v25_tools

    mcp = DummyMCP()
    register_messaging_v25_tools(mcp)
    register_search_v25_tools(mcp)
    register_streams_v25_tools(mcp)
    register_users_v25_tools(mcp)
    register_events_v25_tools(mcp)
    register_files_v25_tools(mcp)
    register_admin_v25_tools(mcp)
