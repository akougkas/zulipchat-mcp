"""Agent communication tools for ZulipChat MCP v0.4.0.

This module is a stub that delegates to agents.py for backwards compatibility.
The actual implementation lives in agents.py to avoid duplication.
"""

from fastmcp import FastMCP


def register_events_tools(mcp: FastMCP) -> None:
    """Register agent communication tools - delegates to agents.py.

    Note: This function is kept for backwards compatibility but does nothing.
    Agent tools are registered via register_agent_tools() in agents.py.
    """
    # Agent tools are now registered via agents.py to avoid duplication
    pass
