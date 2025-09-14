"""ZulipChat MCP Server - CLI argument based like context7."""

import argparse

from fastmcp import FastMCP

from .config import ConfigManager
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
    parser = argparse.ArgumentParser(description="ZulipChat MCP Server")

    # Required credentials
    parser.add_argument("--zulip-email", help="Zulip email address")
    parser.add_argument("--zulip-api-key", help="Zulip API key")
    parser.add_argument(
        "--zulip-site", help="Zulip site URL (e.g., https://yourorg.zulipchat.com)"
    )

    # Optional bot credentials
    parser.add_argument(
        "--zulip-bot-email", help="Bot email for advanced features (optional)"
    )
    parser.add_argument("--zulip-bot-api-key", help="Bot API key (optional)")
    parser.add_argument(
        "--zulip-bot-name", default="Claude Code", help="Bot display name"
    )
    parser.add_argument("--zulip-bot-avatar-url", help="Bot avatar URL (optional)")

    # Debug options
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    # Optional: enable message listener background service
    parser.add_argument(
        "--enable-listener",
        action="store_true",
        help="Enable Zulip message listener service",
    )

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
        debug=args.debug,
    )
    logger.info("Configuration loaded successfully")

    # Initialize database
    logger.info("Initializing database...")
    init_database()
    logger.info("Database initialized successfully")

    # Initialize MCP with modern configuration
    mcp = FastMCP(
        "ZulipChat MCP",
        on_duplicate_tools="warn",           # Warn on duplicate tools
        on_duplicate_resources="error",      # Error on duplicate resources
        on_duplicate_prompts="replace",      # Replace duplicate prompts
        include_fastmcp_meta=True,           # Include metadata for debugging
        mask_error_details=False             # Show detailed errors for debugging
        # Note: debug parameter is deprecated, will be passed to run() method instead
    )

    # Middleware configuration (available in FastMCP 2.12.3)
    # Note: Specific middleware classes may be added in future versions
    # For now, error handling is configured via mask_error_details parameter
    logger.info("FastMCP initialized with modern error handling and metadata support")

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

    logger.info(
        "v2.5.0 architecture consolidation complete: 43+ tools across 9 categories"
    )

    # Start message listener based on CLI flag and/or AFK state watcher
    try:
        import asyncio
        import threading
        import time as _time

        from .core.client import ZulipClientWrapper
        from .services.message_listener import MessageListener
        from .utils.database_manager import DatabaseManager

        client = ZulipClientWrapper(config_manager, use_bot_identity=True)
        dbm = DatabaseManager()
        listener_ref: dict[str, object | None] = {"listener": None, "thread": None}

        def _start_listener() -> None:
            if listener_ref["listener"] is not None:
                return
            listener = MessageListener(client, dbm)
            listener_ref["listener"] = listener

            def _run() -> None:
                asyncio.run(listener.start())

            t = threading.Thread(target=_run, name="zulip-listener", daemon=True)
            listener_ref["thread"] = t
            t.start()
            logger.info("Message listener started (watcher)")

        def _stop_listener() -> None:
            listener = listener_ref.get("listener")
            if listener is None:
                return
            try:
                # type: ignore[attr-defined]
                asyncio.run(listener.stop())  # best-effort
            except Exception:
                pass
            listener_ref["listener"] = None
            listener_ref["thread"] = None
            logger.info("Message listener stopped (watcher)")

        def _afk_watcher() -> None:
            # If CLI explicitly enabled, start immediately
            if args.enable_listener:
                _start_listener()
            # Poll AFK state and toggle listener accordingly
            while True:
                try:
                    state = dbm.get_afk_state() or {}
                    enabled = bool(state.get("is_afk"))
                    has_listener = listener_ref["listener"] is not None
                    if enabled and not has_listener:
                        _start_listener()
                    elif (not enabled) and has_listener and not args.enable_listener:
                        _stop_listener()
                except Exception as _e:
                    logger.error(f"AFK watcher error: {_e}")
                _time.sleep(5)

        threading.Thread(target=_afk_watcher, name="afk-watcher", daemon=True).start()
    except Exception as e:
        logger.error(f"Failed to initialize listener/watcher: {e}")

    logger.info("Starting ZulipChat MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
