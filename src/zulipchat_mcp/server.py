"""ZulipChat MCP Server - CLI argument based like context7."""

import argparse
from mcp.server.fastmcp import FastMCP

from .config import ConfigManager
from .tools import agents, messaging, search, streams
from .utils.database import init_database
from .utils.logging import get_logger, setup_structured_logging


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="ZulipChat MCP Server")
    
    # Required credentials
    parser.add_argument("--zulip-email", help="Zulip email address")
    parser.add_argument("--zulip-api-key", help="Zulip API key")
    parser.add_argument("--zulip-site", help="Zulip site URL (e.g., https://yourorg.zulipchat.com)")
    
    # Optional bot credentials
    parser.add_argument("--zulip-bot-email", help="Bot email for advanced features (optional)")
    parser.add_argument("--zulip-bot-api-key", help="Bot API key (optional)")
    parser.add_argument("--zulip-bot-name", default="Claude Code", help="Bot display name")
    parser.add_argument("--zulip-bot-avatar-url", help="Bot avatar URL (optional)")
    
    # Debug options
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_structured_logging()
    logger = get_logger(__name__)
    
    # Initialize configuration with CLI args
    config_manager = ConfigManager(
        email=args.zulip_email,
        api_key=args.zulip_api_key,
        site=args.zulip_site,
        bot_email=args.zulip_bot_email,
        bot_api_key=args.zulip_bot_api_key,
        bot_name=args.zulip_bot_name,
        bot_avatar_url=args.zulip_bot_avatar_url,
        debug=args.debug
    )
    logger.info("Configuration loaded successfully")
    
    # Initialize database
    logger.info("Initializing database...")
    init_database()
    logger.info("Database initialized successfully")
    
    # Initialize MCP
    mcp = FastMCP("ZulipChat MCP")
    
    # Register tool groups
    messaging.register_messaging_tools(mcp)
    streams.register_stream_tools(mcp)
    agents.register_agent_tools(mcp)
    search.register_search_tools(mcp)
    
    logger.info("Starting ZulipChat MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
