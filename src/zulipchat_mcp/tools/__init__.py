"""MCP tool registrars for ZulipChat MCP."""

from .ai_analytics import register_ai_analytics_tools
from .emoji_messaging import register_emoji_messaging_tools
from .event_management import register_event_management_tools
from .files import register_files_tools
from .mark_messaging import register_mark_messaging_tools
from .messaging import register_messaging_tools
from .schedule_messaging import register_schedule_messaging_tools
from .search import register_search_tools
from .stream_management import register_stream_management_tools
from .system import register_system_tools
from .topic_management import register_topic_management_tools
from .users import register_users_tools

__all__ = [
    "register_messaging_tools",
    "register_schedule_messaging_tools",
    "register_emoji_messaging_tools",
    "register_mark_messaging_tools",
    "register_search_tools",
    "register_stream_management_tools",
    "register_topic_management_tools",
    "register_event_management_tools",
    "register_ai_analytics_tools",
    "register_users_tools",
    "register_files_tools",
    "register_system_tools",
    "register_core_tools",
    "register_extended_tools",
]


def register_core_tools(mcp) -> None:
    """Register 19 core tools for default mode."""
    from .agents import (
        agent_message,
        register_agent,
        request_user_input,
        teleport_chat,
        wait_for_response,
    )
    from .emoji_messaging import add_reaction
    from .mark_messaging import manage_message_flags
    from .messaging import edit_message, get_message, send_message
    from .search import search_messages
    from .stream_management import get_stream_info, get_streams
    from .system import server_info, switch_identity
    from .topic_management import get_stream_topics
    from .users import get_own_user, get_users, resolve_user

    # Messaging (4)
    mcp.tool(name="send_message", description="Send a message to a stream or user.")(
        send_message
    )
    mcp.tool(
        name="edit_message",
        description="Edit message content, topic, or move between streams.",
    )(edit_message)
    mcp.tool(name="get_message", description="Retrieve a single message by ID.")(
        get_message
    )
    mcp.tool(name="add_reaction", description="Add emoji reaction to a message.")(
        add_reaction
    )

    # Search & Discovery (4)
    mcp.tool(
        name="search_messages",
        description="Search messages with filters for stream, topic, sender, time.",
    )(search_messages)
    mcp.tool(name="get_streams", description="List available streams/channels.")(
        get_streams
    )
    mcp.tool(name="get_stream_info", description="Get detailed stream information.")(
        get_stream_info
    )
    mcp.tool(name="get_stream_topics", description="List recent topics in a stream.")(
        get_stream_topics
    )

    # Users (3)
    mcp.tool(
        name="resolve_user",
        description="Resolve display name to email with fuzzy matching.",
    )(resolve_user)
    mcp.tool(name="get_users", description="List all users in the organization.")(
        get_users
    )
    mcp.tool(
        name="get_own_user",
        description="Get current authenticated user's profile.",
    )(get_own_user)

    # Agent Communication (5)
    mcp.tool(
        name="teleport_chat",
        description="Send message to user or channel with fuzzy name resolution.",
    )(teleport_chat)
    mcp.tool(
        name="register_agent",
        description="Register agent instance for tracking and communication.",
    )(register_agent)
    mcp.tool(
        name="agent_message",
        description="Send agent notification via Agents-Channel.",
    )(agent_message)
    mcp.tool(
        name="request_user_input",
        description="Request interactive input from user with options.",
    )(request_user_input)
    mcp.tool(
        name="wait_for_response",
        description="Wait for user reply to an input request.",
    )(wait_for_response)

    # System & Flags (3)
    mcp.tool(
        name="switch_identity",
        description="Switch between user and bot identities.",
    )(switch_identity)
    mcp.tool(
        name="server_info", description="Get server version and capabilities."
    )(server_info)
    mcp.tool(
        name="manage_message_flags",
        description="Mark messages as read/unread or star/unstar.",
    )(manage_message_flags)


def register_extended_tools(mcp) -> None:
    """Register extended tools (merged + remaining originals).

    Call after register_core_tools() to add the full tool set.
    Core tools are already registered; this adds the rest.
    """
    from .agents import (
        afk_mode,
        list_instances,
        manage_task,
        poll_agent_events,
        send_agent_status,
    )
    from .ai_analytics import (
        analyze_stream_with_llm,
        analyze_team_activity_with_llm,
        get_daily_summary,
        intelligent_report_generator,
    )
    from .commands import execute_chain, list_command_types
    from .emoji_messaging import toggle_reaction
    from .event_management import (
        deregister_events,
        get_events,
        listen_events,
        register_events,
    )
    from .files import manage_files, upload_file
    from .mark_messaging import update_message_flags_for_narrow
    from .messaging import cross_post_message
    from .schedule_messaging import (
        get_scheduled_messages,
        manage_scheduled_message,
    )
    from .search import advanced_search, check_messages_match_narrow, construct_narrow
    from .topic_management import agents_channel_topic_ops
    from .users import (
        get_presence,
        get_user,
        get_user_group_members,
        get_user_groups,
        get_user_presence,
        get_user_status,
        is_user_group_member,
        manage_user_mute,
        update_status,
    )

    # Users — merged + remaining (9)
    mcp.tool(name="get_user", description="Look up a user by ID or email.")(get_user)
    mcp.tool(
        name="get_user_status", description="Get user's status text and emoji."
    )(get_user_status)
    mcp.tool(name="update_status", description="Update your own status and emoji.")(
        update_status
    )
    mcp.tool(
        name="get_user_presence", description="Get presence info for a specific user."
    )(get_user_presence)
    mcp.tool(
        name="get_presence", description="Get presence info for all users."
    )(get_presence)
    mcp.tool(name="get_user_groups", description="Get all user groups.")(
        get_user_groups
    )
    mcp.tool(
        name="get_user_group_members", description="Get members of a user group."
    )(get_user_group_members)
    mcp.tool(
        name="is_user_group_member", description="Check if user is in a group."
    )(is_user_group_member)
    mcp.tool(
        name="manage_user_mute", description="Mute or unmute a user."
    )(manage_user_mute)

    # Messaging (2)
    mcp.tool(
        name="cross_post_message", description="Share a message across streams."
    )(cross_post_message)
    mcp.tool(
        name="toggle_reaction", description="Add or remove an emoji reaction."
    )(toggle_reaction)

    # Search (3)
    mcp.tool(
        name="advanced_search",
        description="Multi-faceted search across messages, users, streams.",
    )(advanced_search)
    mcp.tool(
        name="construct_narrow", description="Build a narrow filter for Zulip API."
    )(construct_narrow)
    mcp.tool(
        name="check_messages_match_narrow",
        description="Check if messages match a narrow filter.",
    )(check_messages_match_narrow)

    # Scheduled Messages (2)
    mcp.tool(
        name="get_scheduled_messages", description="Get all scheduled messages."
    )(get_scheduled_messages)
    mcp.tool(
        name="manage_scheduled_message",
        description="Create, update, or delete a scheduled message.",
    )(manage_scheduled_message)

    # Events (4)
    mcp.tool(
        name="register_events", description="Register for real-time event streams."
    )(register_events)
    mcp.tool(name="get_events", description="Poll events from a registered queue.")(
        get_events
    )
    mcp.tool(
        name="listen_events", description="Listen for events with auto queue management."
    )(listen_events)
    mcp.tool(name="deregister_events", description="Deregister an event queue.")(
        deregister_events
    )

    # AI Analytics (4)
    mcp.tool(name="get_daily_summary", description="Get daily message summary.")(
        get_daily_summary
    )
    mcp.tool(
        name="analyze_stream_with_llm",
        description="Analyze stream data with LLM insights.",
    )(analyze_stream_with_llm)
    mcp.tool(
        name="analyze_team_activity_with_llm",
        description="Analyze team activity across streams with LLM.",
    )(analyze_team_activity_with_llm)
    mcp.tool(
        name="intelligent_report_generator",
        description="Generate reports using LLM analysis.",
    )(intelligent_report_generator)

    # Agent Extended (5)
    mcp.tool(
        name="send_agent_status", description="Send agent status update."
    )(send_agent_status)
    mcp.tool(name="manage_task", description="Start, update, or complete a task.")(
        manage_task
    )
    mcp.tool(name="list_instances", description="List registered agent instances.")(
        list_instances
    )
    mcp.tool(
        name="afk_mode", description="Enable, disable, or check AFK mode."
    )(afk_mode)
    mcp.tool(
        name="poll_agent_events", description="Poll unacknowledged agent events."
    )(poll_agent_events)

    # Files (2)
    mcp.tool(name="upload_file", description="Upload a file to Zulip.")(upload_file)
    mcp.tool(
        name="manage_files", description="List, delete, share, or download files."
    )(manage_files)

    # Topics (1)
    mcp.tool(
        name="agents_channel_topic_ops",
        description="Topic operations in Agents-Channel (bot only).",
    )(agents_channel_topic_ops)

    # Commands (2)
    mcp.tool(name="execute_chain", description="Execute a command chain workflow.")(
        execute_chain
    )
    mcp.tool(
        name="list_command_types", description="List available command types."
    )(list_command_types)

    # Raw flag API for power users (1)
    mcp.tool(
        name="update_message_flags_for_narrow",
        description="Update message flags for a narrow (raw API).",
    )(update_message_flags_for_narrow)
