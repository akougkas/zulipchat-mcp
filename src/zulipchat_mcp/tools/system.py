"""System tools for ZulipChat MCP v0.4.0.

System information and identity management tools.
"""

from typing import Any, Literal

from fastmcp import FastMCP

from ..config import get_config_manager
from ..core.client import ZulipClientWrapper


async def switch_identity(identity: Literal["user", "bot"]) -> dict[str, Any]:
    """Switch between user and bot identity contexts."""
    config = get_config_manager()

    try:
        if identity == "bot" and not config.has_bot_credentials():
            return {
                "status": "error",
                "error": "Bot credentials not configured",
                "suggestion": "Set ZULIP_BOT_EMAIL and ZULIP_BOT_API_KEY environment variables",
            }

        # Create client with specified identity
        use_bot = identity == "bot"
        client = ZulipClientWrapper(config, use_bot_identity=use_bot)

        return {
            "status": "success",
            "identity": client.identity,
            "identity_name": client.identity_name,
            "current_email": client.current_email,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def server_info() -> dict[str, Any]:
    """Get ZulipChat MCP server information and capabilities."""
    config = get_config_manager()

    return {
        "status": "success",
        "server_name": "ZulipChat MCP",
        "version": "0.4.3",
        "available_identities": {
            "user": {"available": True, "email": config.config.email},
            "bot": {
                "available": config.has_bot_credentials(),
                "email": config.config.bot_email,
                "name": config.config.bot_name,
            },
        },
        "features": [
            "messaging",
            "search_with_fuzzy_users",
            "stream_management",
            "user_management",
            "event_system",
            "file_uploads",
            "dual_identity",
        ],
        "zulip_site": config.config.site,
    }


def register_system_tools(mcp: FastMCP) -> None:
    """Register system tools with the MCP server."""
    mcp.tool(
        name="switch_identity", description="Switch between user and bot identities"
    )(switch_identity)
    mcp.tool(name="server_info", description="Get server information and capabilities")(
        server_info
    )
