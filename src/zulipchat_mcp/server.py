"""Lightweight MCP server entrypoint for ZulipChat MCP v2."""

from mcp.server.fastmcp import FastMCP

from .utils.logging import get_logger, setup_structured_logging
from .utils.database import init_database
from .tools import messaging, streams, agents, search

# Setup logging
setup_structured_logging()
logger = get_logger(__name__)

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

def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting ZulipChat MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
