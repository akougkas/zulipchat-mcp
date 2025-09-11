"""ZulipChat MCP Server - CLI argument based like context7."""

import argparse
from mcp.server.fastmcp import FastMCP

from .config import ConfigManager
from .tools import agents, commands, messaging, search, streams
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
    # Optional: enable message listener background service
    parser.add_argument("--enable-listener", action="store_true", help="Enable Zulip message listener service")
    
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
    commands.register_command_tools(mcp)
    
    # Start message listener based on CLI flag and/or AFK state watcher
    try:
        import threading
        import time as _time
        import asyncio
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
