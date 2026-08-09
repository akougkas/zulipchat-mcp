"""ZulipChat MCP Server package.

The compatibility patch runs on package import because embedded ASGI and
framework runner entry points can bypass the console script. Import time is the
only shared boundary before those entry points accept MCP traffic, and the patch
is idempotent.
"""

from .core import compat

compat.apply()

__version__ = "0.7.3-beta.1"

__all__: list[str] = []
