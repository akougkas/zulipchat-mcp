"""ZulipChat MCP Server - zuliprc-first configuration."""

import argparse
import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp_tasks import TasksExtension
from mcp.types import Icon

from . import __version__
from .config import init_config_manager
from .core.security import set_file_root, set_unsafe_mode
from .core.skills import register_skills
from .core.snapshots import configure_snapshot_root
from .core.tool_contract import ToolContractMiddleware
from .tools import register_core_tools, register_extended_tools
from .utils.logging import get_logger, setup_structured_logging

# Flags of the agent control plane removed in 0.8.0. Host configurations
# written for 0.7 still pass them, so they are accepted and ignored.
_RETIRED_FLAGS = ("--enable-listener", "--associate-existing-db")

# docs/assets/zulipchat-mcp-icon.svg, inlined so the icon needs no network.
_ICON_SVG_BASE64 = (
    "PHN2ZyB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgdmlld0JveD0iMCAwIDI1NiAyNTYiIHht"
    "bG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgcm9sZT0iaW1nIiBhcmlhLWxhYmVs"
    "PSJadWxpcENoYXQgTUNQIj4KICA8cmVjdCB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgcng9"
    "IjM2IiBmaWxsPSIjMWYyOTM3Ii8+CiAgPHJlY3QgeD0iMzIiIHk9IjQwIiB3aWR0aD0iMTky"
    "IiBoZWlnaHQ9IjE3NiIgcng9IjE4IiBmaWxsPSIjMGVhNWE2Ii8+CiAgPHBhdGggZD0iTTY0"
    "IDg4aDEyOHYxNkg2NHpNNjQgMTIwaDk2djE2SDY0ek02NCAxNTJoNzJ2MTZINjR6IiBmaWxs"
    "PSIjZTVlN2ViIi8+CiAgPGNpcmNsZSBjeD0iMTg4IiBjeT0iMTYwIiByPSIyMCIgZmlsbD0i"
    "IzExMTgyNyIvPgogIDxwYXRoIGQ9Ik0xODggMTQ4djI0TTE3NiAxNjBoMjQiIHN0cm9rZT0i"
    "IzIyYzU1ZSIgc3Ryb2tlLXdpZHRoPSI2IiBzdHJva2UtbGluZWNhcD0icm91bmQiLz4KPC9z"
    "dmc+Cg=="
)
SERVER_ICON = Icon(
    src=f"data:image/svg+xml;base64,{_ICON_SVG_BASE64}",
    mime_type="image/svg+xml",
    sizes=["any"],
)


def account_cache_dir(fingerprint: str) -> Path:
    """Per-account cache shared by every server process for that account."""
    base = os.getenv("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "zulipchat-mcp" / "accounts" / fingerprint / "cache"


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
        help="Allow delete_file to delete uploaded files. Default: SAFE mode.",
    )
    parser.add_argument(
        "--file-root",
        default=os.getenv("ZULIPCHAT_FILE_ROOT"),
        help=(
            "Directory that upload_file and download_file local paths must stay "
            "inside (or set ZULIPCHAT_FILE_ROOT; default: the working directory)."
        ),
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    for flag in _RETIRED_FLAGS:
        parser.add_argument(flag, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--mention-allow", help=argparse.SUPPRESS)
    parser.add_argument(
        "--extended-tools",
        action="store_true",
        help="Register all 53 tools instead of the 13-tool core set.",
    )
    parser.add_argument(
        "--tool-profile",
        choices=["full", "read-only", "ask-owner"],
        default="full",
        help=(
            "Restrict tool discovery and execution: read-only permits only Zulip "
            "reads; ask-owner permits only ask_owner, for agents launched by "
            "zulipchat-mcp-agents."
        ),
    )
    parser.add_argument(
        "--ephemeral-state",
        action="store_true",
        help=(
            "Write no files: read caches stay in memory. For hosts that run the "
            "server where the state directory is not writable, such as a "
            "sandboxed worker."
        ),
    )

    # Transport Options
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help=(
            "Transport to serve on (default: stdio). 'http' runs the "
            "streamable-HTTP transport; on the 2026-07-28 protocol each "
            "request is self-contained."
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
            "ZULIPCHAT_HTTP_AUTH_TOKEN). Required for any non-loopback bind."
        ),
    )
    parser.add_argument(
        "--allowed-host",
        action="append",
        help="Additional trusted HTTP Host (repeatable)",
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        help="Additional trusted browser origin (repeatable)",
    )

    args = parser.parse_args()
    if args.tool_profile == "read-only" and args.unsafe:
        parser.error("The read-only tool profile cannot enable unsafe mode")
    if args.transport == "http":
        if args.auth_token is not None and (
            not args.auth_token.strip()
            or any(char.isspace() for char in args.auth_token)
        ):
            parser.error("HTTP auth token must be non-empty and contain no whitespace")
        if not args.auth_token and args.host not in ("127.0.0.1", "localhost", "::1"):
            parser.error(
                "Non-loopback HTTP requires --auth-token or ZULIPCHAT_HTTP_AUTH_TOKEN"
            )
        if not 1 <= args.port <= 65535:
            parser.error("HTTP port must be between 1 and 65535")

    # Setup logging
    setup_structured_logging("DEBUG" if args.debug else "INFO")
    logger = get_logger(__name__)
    retired = [
        flag
        for flag in (*_RETIRED_FLAGS, "--mention-allow")
        if getattr(args, flag[2:].replace("-", "_"))
    ]
    if retired:
        logger.warning(
            "Ignoring %s: the agent control plane was removed in 0.8.0; "
            "see zulipchat-mcp-agents",
            ", ".join(retired),
        )

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
        raise SystemExit(1)

    logger.info("Configuration loaded successfully")

    # Set global safety mode context
    set_unsafe_mode(args.unsafe)
    if args.file_root and not os.path.isdir(os.path.expanduser(args.file_root)):
        logger.error("--file-root %s is not a directory", args.file_root)
        raise SystemExit(1)
    set_file_root(args.file_root)
    if args.unsafe:
        logger.warning("RUNNING IN UNSAFE MODE - Dangerous tools enabled")

    if not args.ephemeral_state:
        try:
            fingerprint = config_manager.resolved_account().fingerprint
        except ValueError as error:
            logger.error(str(error))
            raise SystemExit(1) from error
        configure_snapshot_root(account_cache_dir(fingerprint))

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

    # Initialize MCP with modern configuration
    mcp = FastMCP(
        "ZulipChat MCP",
        version=__version__,
        website_url="https://github.com/PanStudio/zulipchat-mcp",
        icons=[SERVER_ICON],
        instructions=(
            "ask_owner asks the owner of this Zulip conversation a question."
            if args.tool_profile == "ask-owner"
            else "Zulip for coding agents. send_message takes names; search_messages "
            "reads threads and unread messages compactly; teleport_chat hands the "
            "conversation to the owner's agent bot in Zulip."
        ),
        on_duplicate="warn",
        auth=auth,
        # The tool set is fixed for the life of the process; 2026-07-28 clients
        # may reuse the listing for an hour instead of refetching it.
        cache_ttl=3600,
        # FastMCP protocol tasks are enabled per long-running tool. Keeping the
        # server default forbidden prevents sync/fast tools from being advertised
        # as task-capable by accident.
        tasks=False,
    )

    # Register the SEP-2663 Tasks extension: in FastMCP 4, tools declared with
    # task=TaskConfig(...) are rejected at startup unless this extension is
    # present. Defaults read FASTMCP_DOCKET_* env vars, unchanged from v3.
    mcp.add_extension(TasksExtension())
    mcp.add_middleware(
        ToolContractMiddleware(profile=args.tool_profile, transport=args.transport)
    )
    if args.tool_profile != "ask-owner":  # the skills describe tools it lacks
        register_skills(mcp)

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
        logger.info("Registered extended tool set (53 tools)")
    else:
        logger.info("Registered core tool set (13 tools)")

    logger.info("Starting ZulipChat MCP server (transport=%s)...", args.transport)
    if args.transport == "http":
        mcp.run(
            transport="http",
            host=args.host,
            port=args.port,
            host_origin_protection=True,
            allowed_hosts=args.allowed_host,
            allowed_origins=args.allowed_origin,
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
