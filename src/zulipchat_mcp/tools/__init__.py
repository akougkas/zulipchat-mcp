"""MCP tool registrars for ZulipChat MCP."""

from .messaging import register_messaging_tools
from .schedule_messaging import register_schedule_messaging_tools
from .emoji_messaging import register_emoji_messaging_tools
from .mark_messaging import register_mark_messaging_tools
from .search import register_search_tools
from .stream_management import register_stream_management_tools
from .topic_management import register_topic_management_tools
from .streams import register_streams_tools
from .event_management import register_event_management_tools
from .events import register_events_tools  # Now agent communication
from .users import register_users_tools
from .files import register_files_tools
from .system import register_system_tools

__all__ = [
    "register_messaging_tools",
    "register_schedule_messaging_tools",
    "register_emoji_messaging_tools",
    "register_mark_messaging_tools",
    "register_search_tools",
    "register_stream_management_tools",
    "register_topic_management_tools",
    "register_streams_tools",
    "register_event_management_tools",
    "register_events_tools",
    "register_users_tools",
    "register_files_tools",
    "register_system_tools",
]
