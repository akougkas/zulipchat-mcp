"""ZulipChat MCP Server - zuliprc-first configuration."""

import argparse
import os
from collections.abc import AsyncIterator
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp_tasks import TasksExtension

from . import __version__
from .config import ConfigManager, init_config_manager
from .core import compat
from .core.security import set_unsafe_mode

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
    # Temporary patch: restore ping for 2026-07-28 connections. Must run
    # before any MCP traffic. Remove when upstream (python-sdk #3273) ships
    # a fix and our mcp floor includes it.
    compat.apply()

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

    # Transport Options
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help=(
            "Transport to serve on (default: stdio). 'http' runs the "
            "streamable-HTTP transport; on the 2026-07-28 protocol each "
            "request is self-contained, so replicas sit behind a plain "
            "round-robin load balancer with no sticky sessions."
        ),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for --transport http (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind for --transport http (default: 8000)",
    )
    parser.add_argument(
        "--auth-token",
        default=os.getenv("ZULIPCHAT_HTTP_AUTH_TOKEN"),
        help=(
            "Bearer token required on HTTP requests (or set "
            "ZULIPCHAT_HTTP_AUTH_TOKEN). Strongly recommended for any "
            "non-localhost bind."
        ),
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

    # Server-side LLM analytics: MCP sampling was removed in the 2026-07-28
    # protocol, so analytics tools call a provider owned by this server
    # (see src/zulipchat_mcp/core/llm.py) instead of delegating to the client.
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.debug(
            "ANTHROPIC_API_KEY not set - AI analytics tools return structured data only"
        )

    # HTTP transport auth: require an explicit bearer token when binding
    # beyond localhost unless the operator opts out with a loopback bind.
    auth = None
    if args.transport == "http":
        if args.auth_token:
            from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

            auth = StaticTokenVerifier(
                tokens={args.auth_token: {"client_id": "zulipchat-http", "scopes": []}}
            )
            logger.info("HTTP transport: bearer token auth enabled")
        elif args.host not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(
                "HTTP transport binding to %s WITHOUT --auth-token - any client "
                "that can reach this port can call tools. Set "
                "ZULIPCHAT_HTTP_AUTH_TOKEN or pass --auth-token.",
                args.host,
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
        auth=auth,
        # FastMCP protocol tasks are enabled per long-running tool. Keeping the
        # server default forbidden prevents sync/fast tools from being advertised
        # as task-capable by accident.
        tasks=False,
        lifespan=_build_server_lifespan(config_manager, args.enable_listener),
    )

    # Register the SEP-2663 Tasks extension: in FastMCP 4, tools declared with
    # task=TaskConfig(...) are rejected at startup unless this extension is
    # present. Defaults read FASTMCP_DOCKET_* env vars, unchanged from v3.
    mcp.add_extension(TasksExtension())

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

    logger.info("Starting ZulipChat MCP server (transport=%s)...", args.transport)
    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
