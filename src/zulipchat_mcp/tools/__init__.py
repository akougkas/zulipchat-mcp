"""MCP tool registrars for ZulipChat MCP."""

from .admin_v25 import register_admin_v25_tools
from .events_v25 import register_events_v25_tools
from .files_v25 import register_files_v25_tools
from .messaging_v25 import register_messaging_v25_tools
from .search_v25 import register_search_v25_tools
from .streams_v25 import register_streams_v25_tools
from .users_v25 import register_users_v25_tools

__all__ = [
    "register_messaging_v25_tools",
    "register_streams_v25_tools",
    "register_events_v25_tools",
    "register_users_v25_tools",
    "register_search_v25_tools",
    "register_files_v25_tools",
    "register_admin_v25_tools",
]
