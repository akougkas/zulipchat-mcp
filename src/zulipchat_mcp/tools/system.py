"""System/meta tools to improve client awareness and token efficiency.

Exposes:
- server_info(): Minimal server metadata and identity capabilities
- tool_help(name): On-demand detailed docs for a tool (kept out of default list)
"""

from __future__ import annotations

from typing import Any

from .. import __version__
from ..config import ConfigManager
from ..core.identity import IdentityManager, IdentityType


def server_info() -> dict[str, Any]:
    """Return concise server metadata and identity support.

    Kept short to minimize tokens in tools/list; clients can call for details.
    """
    config = ConfigManager()
    ident = IdentityManager(config)

    available = [t.value for t, i in ident.identities.items() if i is not None]
    current = ident.get_current_identity().type.value if ident.current_identity else None

    return {
        "name": "ZulipChat MCP",
        "version": __version__,
        "features": [
            "tools",  # server exposes tools
        ],
        "identities": {
            "available": available,
            "current": current,
            "bot_supported": config.has_bot_credentials(),
        },
        "docs": {
            "spec": "https://modelcontextprotocol.io/specification/2025-03-26",
            "fastmcp": "https://gofastmcp.com/getting-started/welcome",
        },
        "routing_hints": {
            "reads": "Use user identity for search/list/edit",
            "bot_replies": "Use agents.agent_message to reply in Agents-Channel",
            "send_message": "Use messaging.message for org streams (user identity)",
        },
        "limitations": [
            "File listing is limited by Zulip API; consider message parsing",
            "Analytics subscriber data depends on Zulip client API version",
        ],
    }


def tool_help(name: str) -> dict[str, Any]:
    """Return verbose, on-demand docs for a specific tool name.

    Strategy: Keep default tool descriptions brief; provide deeper help here.
    """
    # Lightweight registry by importing modules that define registrars
    from . import messaging_v25, search_v25, streams_v25, users_v25, events_v25, files_v25
    from . import agents, commands

    candidates: list[tuple[str, Any]] = []

    # Map function objects to docstrings and quick examples
    def add_module(mod: Any) -> None:
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if callable(obj) and getattr(obj, "__module__", "").startswith(mod.__name__):
                candidates.append((attr, obj))

    for mod in [
        messaging_v25,
        search_v25,
        streams_v25,
        users_v25,
        events_v25,
        files_v25,
        agents,
        commands,
    ]:
        add_module(mod)

    # Find exact or close match
    normalized = name.strip()
    for tool_name, fn in candidates:
        if tool_name == normalized:
            doc = (fn.__doc__ or "").strip()
            return {
                "tool": tool_name,
                "module": fn.__module__,
                "doc": doc,
            }

    # Fallback: suggest similar tools
    similar = [t for t, _ in candidates if normalized.lower() in t.lower()]
    return {
        "tool": name,
        "error": "Tool not found",
        "suggestions": similar[:10],
    }


def register_system_tools(mcp: Any) -> None:
    mcp.tool(
        description="Comprehensive server metadata and capabilities: returns ZulipChat MCP server name/version, available identity types (user/bot/admin) with current selection, bot credential availability status, supported features list, routing hints for optimal tool selection, API limitations and workarounds, documentation links (MCP specification, FastMCP guides), and configuration status. Essential for understanding server capabilities, identity management, and optimal tool usage patterns. Use to check identity support before calling identity-specific tools."
    )(server_info)

    mcp.tool(
        description="On-demand detailed documentation for specific tools by name: searches across all tool modules (messaging, streams, search, users, events, files, agents, commands), returns comprehensive docstrings with usage examples, provides module location and function details, suggests similar tools for typos/partial matches, and includes parameter descriptions and return values. Token-efficient approach - avoids bloating tool registry with verbose docs. Use when you need detailed implementation guidance for complex tools or parameter clarification."
    )(tool_help)

    mcp.tool(
        description="Identity management policy and best practices guide: provides clear usage guidelines for USER/BOT/ADMIN identities, specifies when to use each identity type (USER for reads/edits, BOT for agent communication), defines bot usage restrictions (Agents-Channel only), includes security recommendations, explains permission boundaries, and provides routing hints for optimal identity selection. Essential for proper multi-identity tool usage and security compliance. Reference before switching identities or using bot features."
    )(identity_policy)

    mcp.tool(
        description="Bootstrap agent registration with bot identity validation: thin wrapper around agents.register_agent for early agent initialization, validates bot credentials availability, creates agent instance records in database, sets up Agents-Channel communication capability, and returns registration confirmation with IDs. Recommended first step for agent-based workflows. Encourages proper agent registration before using communication tools. Enables agent tracking and session management across the MCP server lifecycle."
    )(bootstrap_agent)


def identity_policy() -> dict[str, Any]:
    """Return concise identity policy guidance for clients.

    - Use USER identity for read/search/edit operations.
    - Use BOT identity only to communicate back in the dedicated agent channel.
    - BOT should not post to arbitrary org streams; keep permissions limited in Zulip.
    """
    return {
        "policy": {
            "default": IdentityType.USER.value,
            "bot_usage": {
                "when": [
                    "Send status or questions back to user via Agents-Channel (use agent_message)",
                    "Schedule/draft messages when applicable",
                ],
                "where": "Agents-Channel (restricted)",
                "never_post": "Other org streams unless explicitly authorized",
            },
        },
        "recommended_channel": "Agents-Channel",
        "notes": [
            "Use agents.agent_message for bot-channel replies (no need for messaging.message)",
            "Ensure bot credentials are configured in .env",
            "User manages Zulip permissions to restrict bot to Agents-Channel",
        ],
    }


def bootstrap_agent(agent_type: str = "claude-code") -> dict[str, Any]:
    """Register an agent instance using bot identity if available.

    Thin wrapper around agents.register_agent to encourage early registration.
    """
    try:
        from . import agents as agent_tools

        return agent_tools.register_agent(agent_type=agent_type)
    except Exception as e:
        return {"status": "error", "error": str(e)}


