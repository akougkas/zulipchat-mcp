"""MCP tool registrars for ZulipChat MCP."""

from fastmcp import FastMCP

from .ai_analytics import register_ai_analytics_tools
from .drafts import register_drafts_tools
from .emoji_messaging import register_emoji_messaging_tools
from .event_management import register_event_management_tools
from .files import register_files_tools
from .mark_messaging import register_mark_messaging_tools
from .messaging import register_messaging_tools
from .registration import optional_background_task, register_tool
from .schedule_messaging import register_schedule_messaging_tools
from .search import register_search_tools
from .stream_management import register_stream_management_tools
from .system import register_system_tools
from .topic_management import register_topic_management_tools
from .users import register_users_tools

__all__ = [
    "register_messaging_tools",
    "register_schedule_messaging_tools",
    "register_drafts_tools",
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


def register_core_tools(mcp: FastMCP) -> None:
    """Register the default tool surface."""
    from .agents import (
        agent_message,
        ensure_agent_session,
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

    interactive_task = optional_background_task(poll_seconds=2)

    # Messaging (4)
    register_tool(
        mcp,
        send_message,
        name="send_message",
        description="Send a message to a stream or user.",
        title="Send message",
    )
    register_tool(
        mcp,
        edit_message,
        name="edit_message",
        description="Edit message content, topic, or move between streams.",
        title="Edit message",
        destructive=True,
        idempotent=True,
    )
    register_tool(
        mcp,
        get_message,
        name="get_message",
        description="Retrieve a single message by ID.",
        title="Get message",
    )
    register_tool(
        mcp,
        add_reaction,
        name="add_reaction",
        description="Add emoji reaction to a message.",
        title="Add reaction",
        idempotent=True,
    )

    # Search & Discovery (4)
    register_tool(
        mcp,
        search_messages,
        name="search_messages",
        description="Search messages with filters for stream, topic, sender, time.",
        title="Search messages",
    )
    register_tool(
        mcp,
        get_streams,
        name="get_streams",
        description="List available streams/channels.",
        title="List streams",
    )
    register_tool(
        mcp,
        get_stream_info,
        name="get_stream_info",
        description="Get detailed stream information.",
        title="Get stream info",
    )
    register_tool(
        mcp,
        get_stream_topics,
        name="get_stream_topics",
        description="List recent topics in a stream.",
        title="List stream topics",
    )

    # Users (3)
    register_tool(
        mcp,
        resolve_user,
        name="resolve_user",
        description="Resolve display name to email with fuzzy matching.",
        title="Resolve user",
    )
    register_tool(
        mcp,
        get_users,
        name="get_users",
        description="List all users in the organization.",
        title="List users",
    )
    register_tool(
        mcp,
        get_own_user,
        name="get_own_user",
        description="Get current authenticated user's profile.",
        title="Get own user",
    )

    # Agent Communication (6)
    register_tool(
        mcp,
        teleport_chat,
        name="teleport_chat",
        description="Send message to user or channel with fuzzy name resolution.",
        title="Teleport chat",
        task=interactive_task,
    )
    register_tool(
        mcp,
        register_agent,
        name="register_agent",
        description="Register or update a stable agent profile for Zulip control.",
        title="Register agent",
        idempotent=True,
    )
    register_tool(
        mcp,
        ensure_agent_session,
        name="ensure_agent_session",
        description="Create or refresh the Zulip topic binding for an agent session.",
        title="Ensure agent session",
        idempotent=True,
        open_world=False,
    )
    register_tool(
        mcp,
        agent_message,
        name="agent_message",
        description="Send a session-scoped message into the bound Zulip topic.",
        title="Send agent message",
    )
    register_tool(
        mcp,
        request_user_input,
        name="request_user_input",
        description="Request a question or approval response from the owner in-topic.",
        title="Request user input",
    )
    register_tool(
        mcp,
        wait_for_response,
        name="wait_for_response",
        description="Wait for a persisted agent request response.",
        title="Wait for response",
        idempotent=True,
        task=interactive_task,
    )

    # System & Flags (3)
    register_tool(
        mcp,
        switch_identity,
        name="switch_identity",
        description="Switch between user and bot identities.",
        title="Switch identity",
        idempotent=True,
        open_world=False,
    )
    register_tool(
        mcp,
        server_info,
        name="server_info",
        description="Get server version and capabilities.",
        title="Get server info",
        open_world=False,
    )
    register_tool(
        mcp,
        manage_message_flags,
        name="manage_message_flags",
        description="Mark messages as read/unread or star/unstar.",
        title="Manage message flags",
        idempotent=True,
    )


def register_extended_tools(mcp: FastMCP) -> None:
    """Register extended tools (merged + remaining originals).

    Call after register_core_tools() to add the full tool set.
    Core tools are already registered; this adds the rest.
    """
    from .agents import (
        close_agent_session,
        list_instances,
        list_sessions,
        manage_task,
        poll_agent_events,
        send_agent_status,
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

    listener_task = optional_background_task(poll_seconds=5)

    # Users — merged + remaining (9)
    register_tool(
        mcp,
        get_user,
        name="get_user",
        description="Look up a user by ID or email.",
        title="Get user",
    )
    register_tool(
        mcp,
        get_user_status,
        name="get_user_status",
        description="Get user's status text and emoji.",
        title="Get user status",
    )
    register_tool(
        mcp,
        update_status,
        name="update_status",
        description="Update your own status and emoji.",
        title="Update status",
        idempotent=True,
    )
    register_tool(
        mcp,
        get_user_presence,
        name="get_user_presence",
        description="Get presence info for a specific user.",
        title="Get user presence",
    )
    register_tool(
        mcp,
        get_presence,
        name="get_presence",
        description="Get presence info for all users.",
        title="Get all presence",
    )
    register_tool(
        mcp,
        get_user_groups,
        name="get_user_groups",
        description="Get all user groups.",
        title="List user groups",
    )
    register_tool(
        mcp,
        get_user_group_members,
        name="get_user_group_members",
        description="Get members of a user group.",
        title="List user group members",
    )
    register_tool(
        mcp,
        is_user_group_member,
        name="is_user_group_member",
        description="Check if user is in a group.",
        title="Check user group membership",
    )
    register_tool(
        mcp,
        manage_user_mute,
        name="manage_user_mute",
        description="Mute or unmute a user.",
        title="Mute or unmute user",
        idempotent=True,
    )

    # Messaging (2)
    register_tool(
        mcp,
        cross_post_message,
        name="cross_post_message",
        description="Share a message across streams.",
        title="Cross-post message",
    )
    register_tool(
        mcp,
        toggle_reaction,
        name="toggle_reaction",
        description="Add or remove an emoji reaction.",
        title="Toggle reaction",
        idempotent=True,
    )

    # Search (3)
    register_tool(
        mcp,
        advanced_search,
        name="advanced_search",
        description="Multi-faceted search across messages, users, streams.",
        title="Advanced search",
    )
    register_tool(
        mcp,
        construct_narrow,
        name="construct_narrow",
        description="Build a narrow filter for Zulip API.",
        title="Construct narrow",
        open_world=False,
    )
    register_tool(
        mcp,
        check_messages_match_narrow,
        name="check_messages_match_narrow",
        description="Check if messages match a narrow filter.",
        title="Check narrow match",
    )

    # Scheduled Messages (2)
    register_tool(
        mcp,
        get_scheduled_messages,
        name="get_scheduled_messages",
        description="Get all scheduled messages.",
        title="List scheduled messages",
    )
    register_tool(
        mcp,
        manage_scheduled_message,
        name="manage_scheduled_message",
        description="Create, update, or delete a scheduled message.",
        title="Manage scheduled message",
        destructive=True,
    )

    # Drafts (4)
    register_drafts_tools(mcp)

    # Events (4)
    register_tool(
        mcp,
        register_events,
        name="register_events",
        description="Register for real-time event streams.",
        title="Register event queue",
    )
    register_tool(
        mcp,
        get_events,
        name="get_events",
        description="Poll events from a registered queue.",
        title="Get events",
        idempotent=True,
    )
    register_tool(
        mcp,
        listen_events,
        name="listen_events",
        description="Listen for events with auto queue management.",
        title="Listen for events",
        task=listener_task,
    )
    register_tool(
        mcp,
        deregister_events,
        name="deregister_events",
        description="Deregister an event queue.",
        title="Deregister event queue",
        idempotent=True,
    )

    # AI Analytics (4)
    register_ai_analytics_tools(mcp)

    # Agent Extended
    register_tool(
        mcp,
        send_agent_status,
        name="send_agent_status",
        description="Send agent status update.",
        title="Send agent status",
        open_world=False,
    )
    register_tool(
        mcp,
        manage_task,
        name="manage_task",
        description="Start, update, or complete a task.",
        title="Manage task",
        open_world=False,
    )
    register_tool(
        mcp,
        list_sessions,
        name="list_sessions",
        description="List known agent sessions.",
        title="List agent sessions",
        open_world=False,
    )
    register_tool(
        mcp,
        list_instances,
        name="list_instances",
        description="Compatibility alias for listing sessions.",
        title="List agent instances",
        open_world=False,
    )
    register_tool(
        mcp,
        close_agent_session,
        name="close_agent_session",
        description="Close a session binding and optionally announce the result.",
        title="Close agent session",
    )
    register_tool(
        mcp,
        poll_agent_events,
        name="poll_agent_events",
        description=(
            "Read persisted owner session events, or set mentions_stream for "
            "event-fed bot mentions, or direct_messages=true for every direct or "
            "group-direct message to the bot (exclusive with mentions_stream; "
            "events carry recipients and reply_to). Retain a host-owned "
            "after_message_id cursor; wait_seconds<=25 waits locally without "
            "refetching history. Only senders allowed by --mention-allow "
            "(default: the owner) appear in events; others appear in "
            "ignored_unauthorized without content."
        ),
        title="Poll agent events",
    )

    # Files (2)
    register_tool(
        mcp,
        upload_file,
        name="upload_file",
        description="Upload a file to Zulip.",
        title="Upload file",
    )
    register_tool(
        mcp,
        manage_files,
        name="manage_files",
        description="List, delete, share, or download files.",
        title="Manage files",
        destructive=True,
    )

    # Topics (1)
    register_tool(
        mcp,
        agents_channel_topic_ops,
        name="agents_channel_topic_ops",
        description="Topic operations in Agents-Channel (bot only).",
        title="Manage Agents-Channel topics",
        destructive=True,
    )

    # Commands (2)
    register_tool(
        mcp,
        execute_chain,
        name="execute_chain",
        description="Execute a command chain workflow.",
        title="Execute command chain",
    )
    register_tool(
        mcp,
        list_command_types,
        name="list_command_types",
        description="List available command types.",
        title="List command types",
        open_world=False,
    )

    # Raw flag API for power users (1)
    register_tool(
        mcp,
        update_message_flags_for_narrow,
        name="update_message_flags_for_narrow",
        description="Update message flags for a narrow (raw API).",
        title="Update message flags for narrow",
        idempotent=True,
    )
