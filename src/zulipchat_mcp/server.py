"""ZulipChat MCP Server - zuliprc-first configuration."""

import argparse
import os
from collections.abc import AsyncIterator
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from . import __version__
from .config import ConfigManager, init_config_manager
from .core.security import set_unsafe_mode

# Optional: Anthropic sampling handler for LLM analytics fallback
try:
    from fastmcp.client.sampling.handlers.anthropic import AnthropicSamplingHandler

    anthropic_available = True
except ImportError:
    anthropic_available = False

# Optional service manager for background services
try:
    from .core.service_manager import init_service_manager, shutdown_service_manager

    service_manager_available = True
except ImportError:
    service_manager_available = False

from .tools import register_core_tools, register_extended_tools

try:
    from .utils.database import init_database

    database_available = True
except ImportError:
    database_available = False

from .utils.logging import get_logger, setup_structured_logging


def _build_server_lifespan(config_manager: ConfigManager, enable_listener: bool) -> Any:
    """Build a FastMCP lifespan for ZulipChat background services."""

    @lifespan
    async def server_lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
        if not service_manager_available:
            yield {}
            return

        svc = init_service_manager(config_manager, enable_listener=enable_listener)
        if enable_listener:
            svc.start()
        try:
            yield {"service_manager": svc}
        finally:
            shutdown_service_manager()

    return server_lifespan


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(
        description="ZulipChat MCP Server - Integrates Zulip Chat with AI assistants",
        epilog=(
            "Configuration requires either a zuliprc file "
            "(explicit or auto-discovered) or environment variables "
            "(ZULIP_EMAIL, ZULIP_API_KEY, ZULIP_SITE)."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
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
    parser.add_argument(
        "--extended-tools",
        action="store_true",
        help="Register all tools (60) instead of the core set (20).",
    )

    args = parser.parse_args()

    # Setup logging
    setup_structured_logging("DEBUG" if args.debug else "INFO")
    logger = get_logger(__name__)

    # Initialize configuration (zuliprc files and/or env credentials)
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
        logger.debug(
            "ANTHROPIC_API_KEY not set - LLM analytics will require client sampling support"
        )

    # Initialize MCP with modern configuration
    mcp = FastMCP(
        "ZulipChat MCP",
        version=__version__,
        website_url="https://github.com/akougkas/zulipchat-mcp",
        instructions=(
            "Use ZulipChat MCP to bind coding agents to Zulip topics, send lifecycle "
            "updates, request approvals, and read steering commands from the topic owner."
        ),
        on_duplicate="warn",
        # FastMCP protocol tasks are enabled per long-running tool. Keeping the
        # server default forbidden prevents sync/fast tools from being advertised
        # as task-capable by accident.
        tasks=False,
        lifespan=_build_server_lifespan(config_manager, args.enable_listener),
        sampling_handler=sampling_handler,
        sampling_handler_behavior="fallback",  # Use only when client doesn't support sampling
    )

    logger.info("FastMCP initialized successfully")

    # Determine tool mode
    extended = args.extended_tools or os.getenv("ZULIPCHAT_EXTENDED_TOOLS", "0") in (
        "1",
        "true",
        "True",
    )

    # Register tools
    register_core_tools(mcp)

    if extended:
        register_extended_tools(mcp)
        logger.info("Registered extended tool set (60 tools)")
    else:
        logger.info("Registered core tool set (20 tools)")

    # Warm user/stream caches for fast fuzzy resolution
    try:
        from .config import get_client

        _warmup_client = get_client()
        _warmup_client.get_users()  # populates user_cache via client wrapper
        _warmup_client.get_streams()  # populates stream_cache via client wrapper
        logger.info("User and stream caches warmed")
    except Exception as e:
        logger.debug(f"Cache warmup skipped: {e}")

    logger.info("Starting ZulipChat MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
