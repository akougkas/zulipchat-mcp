"""ZulipChat MCP Server - Environment-first configuration."""

import argparse

from fastmcp import FastMCP

from .config import ConfigManager
from .core.service_manager import ServiceManager
from .tools import (
    register_events_v25_tools,
    register_files_v25_tools,
    register_messaging_v25_tools,
    register_search_v25_tools,
    register_streams_v25_tools,
    register_system_tools,
    register_users_v25_tools,
)
from .utils.database import init_database
from .utils.logging import get_logger, setup_structured_logging


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(
        description="ZulipChat MCP Server - Integrates Zulip Chat with AI assistants",
        epilog="Environment variables take priority over CLI arguments."
    )

    # Optional CLI arguments (environment variables take priority)
    parser.add_argument("--zulip-email", help="Zulip email (fallback for ZULIP_EMAIL)")
    parser.add_argument("--zulip-api-key", help="Zulip API key (fallback for ZULIP_API_KEY)")
    parser.add_argument("--zulip-site", help="Zulip site URL (fallback for ZULIP_SITE)")

    # Optional bot credentials
    parser.add_argument("--zulip-bot-email", help="Bot email (fallback for ZULIP_BOT_EMAIL)")
    parser.add_argument("--zulip-bot-api-key", help="Bot API key (fallback for ZULIP_BOT_API_KEY)")
    parser.add_argument("--zulip-bot-name", help="Bot display name (fallback for ZULIP_BOT_NAME)")
    parser.add_argument("--zulip-bot-avatar-url", help="Bot avatar URL (fallback for ZULIP_BOT_AVATAR_URL)")

    # Service options
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--enable-listener", action="store_true", help="Enable message listener service")

    args = parser.parse_args()

    # Setup logging
    setup_structured_logging()
    logger = get_logger(__name__)

    # Initialize configuration (environment-first, CLI fallback)
    config_manager = ConfigManager(
        email=args.zulip_email,
        api_key=args.zulip_api_key,
        site=args.zulip_site,
        bot_email=args.zulip_bot_email,
        bot_api_key=args.zulip_bot_api_key,
        bot_name=args.zulip_bot_name,
        bot_avatar_url=args.zulip_bot_avatar_url,
        debug=args.debug,
    )

    # Validate configuration
    if not config_manager.validate_config():
        logger.error("Invalid configuration detected")
        return

    logger.info("Configuration loaded successfully")

    # Initialize database
    init_database()
    logger.info("Database initialized")

    # Initialize MCP with modern configuration
    mcp = FastMCP(
        "ZulipChat MCP",
        on_duplicate_tools="warn",           # Warn on duplicate tools
        on_duplicate_resources="error",      # Error on duplicate resources
        on_duplicate_prompts="replace",      # Replace duplicate prompts
        include_fastmcp_meta=True,           # Include metadata for debugging
        mask_error_details=False             # Show detailed errors for debugging
    )

    logger.info("FastMCP initialized successfully")

    # Register V2.5.0 consolidated tools
    logger.info("Registering v2.5.0 consolidated tools...")
    register_messaging_v25_tools(
        mcp
    )  # Replaces: send_message, get_messages, edit_message, add_reaction
    register_streams_v25_tools(
        mcp
    )  # Replaces: get_streams, create_stream, rename_stream, archive_stream
    register_events_v25_tools(
        mcp
    )  # Replaces: register_agent, poll_agent_events (agent system)
    register_users_v25_tools(mcp)  # New: Identity-aware user management
    register_search_v25_tools(mcp)  # Replaces: search_messages, get_daily_summary
    register_files_v25_tools(mcp)  # New: File management with security
    # System tools: server info and per-tool help
    register_system_tools(mcp)

    # Register ONLY agent tools (no conflicts, needed for AFK mode and direct imports)
    # These are specialized tools that don't have v2.5.0 equivalents
    from .tools import agents

    agents.register_agent_tools(mcp)

    # Register command tools (needed for workflow chains)
    from .tools import commands

    commands.register_command_tools(mcp)

    # Server capabilities are handled by the underlying MCP protocol
    # FastMCP 2.12.3 handles capability negotiation automatically

    logger.info("Tool registration complete: 43+ tools across 9 categories")

    # Start background services (message listener, AFK watcher)
    service_manager = ServiceManager(config_manager, enable_listener=args.enable_listener)
    service_manager.start()

    logger.info("Starting ZulipChat MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
