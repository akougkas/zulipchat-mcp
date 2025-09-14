"""ZulipChat MCP Server - Environment-first configuration."""

import argparse

from fastmcp import FastMCP

from .config import ConfigManager
# Optional service manager for background services
try:
    from .core.service_manager import ServiceManager
    service_manager_available = True
except ImportError:
    service_manager_available = False

from .tools import (
    register_messaging_tools,
    register_schedule_messaging_tools,
    register_emoji_messaging_tools,
    register_mark_messaging_tools,
    register_search_tools,
    register_stream_management_tools,
    register_topic_management_tools,
    register_streams_tools,
    register_event_management_tools,
    register_events_tools,  # Now agent communication
    register_users_tools,
    register_files_tools,
    register_system_tools,
)
try:
    from .utils.database import init_database
    database_available = True
except ImportError:
    database_available = False

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

    # Initialize database (optional for agent features)
    if database_available:
        try:
            init_database()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
    else:
        logger.info("Database not available (agent features disabled)")

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

    # Register decoupled tools by API domain
    logger.info("Registering v2.5.1 decoupled tools...")
    register_messaging_tools(mcp)          # Core send/edit operations
    register_schedule_messaging_tools(mcp) # Scheduled message management
    register_emoji_messaging_tools(mcp)    # Emoji reactions
    register_mark_messaging_tools(mcp)     # Message flag updates
    register_search_tools(mcp)             # Search with narrow construction
    register_stream_management_tools(mcp)  # Stream CRUD operations
    register_topic_management_tools(mcp)   # Topic operations
    register_streams_tools(mcp)            # Stream analytics and settings
    register_event_management_tools(mcp)   # Core event system
    register_events_tools(mcp)             # Agent communication
    register_users_tools(mcp)              # READ-ONLY user operations
    register_files_tools(mcp)              # File uploads
    register_system_tools(mcp)             # System info and identity switching

    # Optional: Register agent tools if available (for backward compatibility)
    try:
        from .tools import agents
        agents.register_agent_tools(mcp)
        logger.info("Agent tools registered")
    except ImportError:
        logger.debug("Agent tools not available (optional)")

    try:
        from .tools import commands
        commands.register_command_tools(mcp)
        logger.info("Command tools registered")
    except ImportError:
        logger.debug("Command tools not available (optional)")

    # Server capabilities are handled by the underlying MCP protocol
    # FastMCP 2.12.3 handles capability negotiation automatically

    logger.info("Tool registration complete: Simplified tools across 7 categories")

    # Start background services (message listener, AFK watcher) if available
    if service_manager_available and args.enable_listener:
        try:
            service_manager = ServiceManager(config_manager, enable_listener=args.enable_listener)
            service_manager.start()
            logger.info("Background services started")
        except Exception as e:
            logger.warning(f"Could not start background services: {e}")
    else:
        logger.info("Background services disabled")

    logger.info("Starting ZulipChat MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
