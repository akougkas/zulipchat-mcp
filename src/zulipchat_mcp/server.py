"""ZulipChat MCP Server - zuliprc-first configuration."""

import argparse
import os

from fastmcp import FastMCP

from .config import init_config_manager
from .core.security import set_unsafe_mode

# Optional: Anthropic sampling handler for LLM analytics fallback
try:
    from fastmcp.client.sampling.handlers.anthropic import AnthropicSamplingHandler

    anthropic_available = True
except ImportError:
    anthropic_available = False

# Optional service manager for background services
try:
    from .core.service_manager import ServiceManager

    service_manager_available = True
except ImportError:
    service_manager_available = False

from .tools import (
    register_ai_analytics_tools,
    register_emoji_messaging_tools,
    register_event_management_tools,
    register_events_tools,  # Now agent communication
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
        epilog="Configuration via zuliprc files is required.",
    )

    # Configuration Files
    parser.add_argument(
        "--zulip-config-file",
        help="Path to user zuliprc file (default: searches standard locations)",
    )
    parser.add_argument(
        "--zulip-bot-config-file",
        help="Path to bot zuliprc file (optional, for dual identity)",
    )

    # Safety & Operational Options
    parser.add_argument(
        "--unsafe",
        action="store_true",
        help="Enable dangerous tools (delete messages/users, mass unsubscribe). Default: SAFE mode.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--enable-listener", action="store_true", help="Enable message listener service"
    )

    args = parser.parse_args()

    # Setup logging
    setup_structured_logging()
    logger = get_logger(__name__)

    # Initialize configuration (zuliprc only)
    config_manager = init_config_manager(
        config_file=args.zulip_config_file,
        bot_config_file=args.zulip_bot_config_file,
        debug=args.debug,
    )

    # Validate configuration
    if not config_manager.validate_config():
        logger.error(
            "Invalid configuration. Please run 'uv run zulipchat-mcp-setup' first."
        )
        return

    logger.info("Configuration loaded successfully")

    # Set global safety mode context
    set_unsafe_mode(args.unsafe)
    if args.unsafe:
        logger.warning("RUNNING IN UNSAFE MODE - Dangerous tools enabled")

    # Initialize database (optional for agent features)
    if database_available:
        try:
            init_database()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
    else:
        logger.info("Database not available (agent features disabled)")

    # Configure sampling handler for LLM analytics (fallback when client doesn't support)
    sampling_handler = None
    if anthropic_available and os.getenv("ANTHROPIC_API_KEY"):
        sampling_handler = AnthropicSamplingHandler(
            default_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        )
        logger.info("Anthropic sampling handler configured (fallback mode)")
    elif anthropic_available:
        logger.debug("ANTHROPIC_API_KEY not set - LLM analytics will require client sampling support")

    # Initialize MCP with modern configuration
    mcp = FastMCP(
        "ZulipChat MCP",
        on_duplicate_tools="warn",
        on_duplicate_resources="error",
        on_duplicate_prompts="replace",
        include_fastmcp_meta=True,
        sampling_handler=sampling_handler,
        sampling_handler_behavior="fallback",  # Use only when client doesn't support sampling
    )

    logger.info("FastMCP initialized successfully")

    # Register all tools
    # Safety mode is enforced at the tool level via @require_unsafe_mode decorator
    logger.info("Registering v0.5.0 tools...")

    # Core messaging
    register_messaging_tools(mcp)  # Send/Edit messages
    register_emoji_messaging_tools(mcp)  # Reactions
    register_schedule_messaging_tools(mcp)  # Scheduled messages
    register_mark_messaging_tools(mcp)  # Read receipts

    # Discovery & Search (read-only)
    register_search_tools(mcp)  # Message search
    register_stream_management_tools(mcp)  # Stream info
    register_topic_management_tools(mcp)  # Topic operations
    register_users_tools(mcp)  # User info
    register_ai_analytics_tools(mcp)  # Analytics

    # System & Events
    register_system_tools(mcp)  # Identity management
    register_events_tools(mcp)  # Agent communication
    register_event_management_tools(mcp)  # Event queue management
    register_files_tools(mcp)  # File uploads

    # Optional: Register agent tools if available
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
            service_manager = ServiceManager(
                config_manager, enable_listener=args.enable_listener
            )
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
