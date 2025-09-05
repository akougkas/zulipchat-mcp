"""ZulipChat MCP Server."""

from zulipchat_mcp.client import ZulipClientWrapper
from zulipchat_mcp.config import ConfigManager
from zulipchat_mcp.exceptions import ZulipMCPError
from zulipchat_mcp.server import mcp

__all__ = [
    "mcp",
    "ZulipClientWrapper",
    "ConfigManager",
    "ZulipMCPError",
]

__version__ = "1.3.0"
