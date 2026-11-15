"""MCP tool registry for ZulipChat MCP.

Descriptions lead with one self-contained sentence: hosts that search tools
lazily (Clio's gateway, Claude Code's tool search) show only that sentence.
"""

from fastmcp import FastMCP

from .registration import optional_background_task, register_tool

__all__ = ["register_core_tools", "register_extended_tools", "CORE_TOOLS"]

CORE_TOOLS = (
    "send_message",
    "reply",
    "teleport_chat",
    "wait_for_mentions",
    "edit_message",
    "add_reaction",
    "get_message",
    "search_messages",
    "get_streams",
    "get_stream_topics",
    "resolve_user",
    "get_users",
    "manage_message_flags",
    "register_agent",
    "ensure_agent_session",
    "agent_message",
    "request_user_input",
    "wait_for_response",
    "poll_agent_events",
    "server_info",
    "switch_identity",
)


def register_core_tools(mcp: FastMCP) -> None:
    """Register the default tool surface."""
    from .agents import (
        agent_message,
        ensure_agent_session,
        poll_agent_events,
        register_agent,
        request_user_input,
        wait_for_response,
    )
    from .emoji_messaging import add_reaction
    from .inbox import reply, teleport_chat, wait_for_mentions
    from .mark_messaging import manage_message_flags
    from .messaging import edit_message, get_message, send_message
    from .search import search_messages
    from .stream_management import get_streams
    from .system import server_info, switch_identity
    from .topic_management import get_stream_topics
    from .users import get_users, resolve_user

    waiting = optional_background_task(poll_seconds=2)

    # Messaging
    register_tool(
        mcp,
        send_message,
        name="send_message",
        description=(
            "Send a Zulip message to people by name, email or ID, or to a "
            "#channel topic, in one call."
        ),
        title="Send message",
    )
    register_tool(
        mcp,
        edit_message,
        name="edit_message",
        description="Edit a Zulip message's text, rename its topic, or move it.",
        title="Edit message",
        destructive=True,
        idempotent=True,
    )
    register_tool(
        mcp,
        add_reaction,
        name="add_reaction",
        description="React to a Zulip message with an emoji, or remove=True to undo.",
        title="Add reaction",
        idempotent=True,
    )
    register_tool(
        mcp,
        get_message,
        name="get_message",
        description="Fetch one Zulip message by ID.",
        title="Get message",
    )
    register_tool(
        mcp,
        search_messages,
        name="search_messages",
        description=(
            "Read or search Zulip messages: a channel topic's latest messages, "
            "unread or mentions, or text, sender and time filters."
        ),
        title="Search messages",
    )

    # Bot inbox: the owner talks to the agent through the bot.
    register_tool(
        mcp,
        wait_for_mentions,
        name="wait_for_mentions",
        description=(
            "Wait for the owner to @-mention or DM the bot in Zulip and return "
            "their requests; answer each with reply."
        ),
        title="Wait for mentions",
        task=waiting,
    )
    register_tool(
        mcp,
        reply,
        name="reply",
        description=(
            "Reply as the bot to a wait_for_mentions request, in the "
            "conversation it came from."
        ),
        title="Reply to request",
    )
    register_tool(
        mcp,
        teleport_chat,
        name="teleport_chat",
        description=(
            "Hand this conversation to Zulip: the bot DMs the owner or opens a "
            "channel topic, and replies arrive via wait_for_mentions."
        ),
        title="Teleport chat to Zulip",
        task=waiting,
    )

    # Discovery
    register_tool(
        mcp,
        get_streams,
        name="get_streams",
        description="List Zulip channels (streams) you can see or are subscribed to.",
        title="List channels",
    )
    register_tool(
        mcp,
        get_stream_topics,
        name="get_stream_topics",
        description="List the recent topics in a Zulip channel.",
        title="List channel topics",
    )
    register_tool(
        mcp,
        resolve_user,
        name="resolve_user",
        description="Find a Zulip user's email and ID from a name.",
        title="Resolve user",
    )
    register_tool(
        mcp,
        get_users,
        name="get_users",
        description="List Zulip organization members.",
        title="List users",
    )
    register_tool(
        mcp,
        manage_message_flags,
        name="manage_message_flags",
        description="Mark Zulip messages read or unread, or star and unstar them.",
        title="Manage message flags",
        idempotent=True,
    )

    # Agent sessions bound to a topic (hook-driven hosts such as Claude Code).
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
        description="Post a lifecycle update into an agent session's bound topic.",
        title="Send agent message",
    )
    register_tool(
        mcp,
        request_user_input,
        name="request_user_input",
        description="Ask the owner a question or approval in an agent session topic.",
        title="Request user input",
    )
    register_tool(
        mcp,
        wait_for_response,
        name="wait_for_response",
        description="Wait for the owner's answer to a request_user_input request.",
        title="Wait for response",
        idempotent=True,
        task=waiting,
    )
    register_tool(
        mcp,
        poll_agent_events,
        name="poll_agent_events",
        description=(
            "Read owner steering events for a bound agent session. For bot "
            "mentions and DMs use wait_for_mentions."
        ),
        title="Poll agent events",
    )

    # System
    register_tool(
        mcp,
        server_info,
        name="server_info",
        description="Show the connected Zulip account, identities and enabled tools.",
        title="Server info",
        open_world=False,
    )
    register_tool(
        mcp,
        switch_identity,
        name="switch_identity",
        description="Switch the default Zulip identity between user and bot.",
        title="Switch identity",
        open_world=False,
        idempotent=True,
    )


def register_extended_tools(mcp: FastMCP) -> None:
    """Register the rest of the Zulip API surface after the core tools."""
    from .agents import close_agent_session, list_sessions
    from .ai_analytics import register_ai_analytics_tools
    from .drafts import register_drafts_tools
    from .event_management import (
        deregister_events,
        get_events,
        listen_events,
        register_events,
    )
    from .files import manage_files, upload_file
    from .mark_messaging import update_message_flags_for_narrow
    from .messaging import cross_post_message
    from .schedule_messaging import get_scheduled_messages, manage_scheduled_message
    from .search import check_messages_match_narrow
    from .stream_management import get_stream_info
    from .users import (
        get_own_user,
        get_presence,
        get_user,
        get_user_group_members,
        get_user_groups,
        get_user_presence,
        get_user_status,
        manage_user_mute,
        update_status,
    )

    # Users
    for fn, name, description, title in (
        (get_own_user, "get_own_user", "Get your own Zulip profile.", "Get own user"),
        (get_user, "get_user", "Look up a Zulip user by ID or email.", "Get user"),
        (
            get_user_status,
            "get_user_status",
            "Get a Zulip user's status text and emoji.",
            "Get user status",
        ),
        (
            get_user_presence,
            "get_user_presence",
            "Get whether one Zulip user is active, idle or offline.",
            "Get user presence",
        ),
        (
            get_presence,
            "get_presence",
            "Get presence for every Zulip user.",
            "Get all presence",
        ),
        (
            get_user_groups,
            "get_user_groups",
            "List Zulip user groups.",
            "List user groups",
        ),
        (
            get_user_group_members,
            "get_user_group_members",
            "List the members of a Zulip user group.",
            "List user group members",
        ),
        (
            get_stream_info,
            "get_stream_info",
            "Get one Zulip channel's settings, description and subscribers.",
            "Get channel info",
        ),
        (
            get_scheduled_messages,
            "get_scheduled_messages",
            "List your scheduled Zulip messages.",
            "List scheduled messages",
        ),
        (
            check_messages_match_narrow,
            "check_messages_match_narrow",
            "Check which message IDs match a Zulip narrow.",
            "Check narrow match",
        ),
    ):
        register_tool(mcp, fn, name=name, description=description, title=title)

    register_tool(
        mcp,
        update_status,
        name="update_status",
        description="Set your Zulip status text and emoji.",
        title="Update status",
        idempotent=True,
    )
    register_tool(
        mcp,
        manage_user_mute,
        name="manage_user_mute",
        description="Mute or unmute a Zulip user.",
        title="Mute or unmute user",
        idempotent=True,
    )
    register_tool(
        mcp,
        cross_post_message,
        name="cross_post_message",
        description="Share an existing Zulip message into other channels.",
        title="Cross-post message",
    )
    register_tool(
        mcp,
        manage_scheduled_message,
        name="manage_scheduled_message",
        description="Create, update, or delete a scheduled Zulip message.",
        title="Manage scheduled message",
        destructive=True,
    )
    register_drafts_tools(mcp)

    # Raw event queues
    register_tool(
        mcp,
        register_events,
        name="register_events",
        description="Register a raw Zulip event queue.",
        title="Register event queue",
    )
    register_tool(
        mcp,
        get_events,
        name="get_events",
        description="Poll events from a raw Zulip event queue.",
        title="Get events",
        idempotent=True,
    )
    register_tool(
        mcp,
        listen_events,
        name="listen_events",
        description="Listen for Zulip events with automatic queue management.",
        title="Listen for events",
        task=optional_background_task(poll_seconds=5),
    )
    register_tool(
        mcp,
        deregister_events,
        name="deregister_events",
        description="Delete a raw Zulip event queue.",
        title="Deregister event queue",
        idempotent=True,
    )

    register_ai_analytics_tools(mcp)

    register_tool(
        mcp,
        list_sessions,
        name="list_sessions",
        description="List known agent sessions and their Zulip topics.",
        title="List agent sessions",
        open_world=False,
    )
    register_tool(
        mcp,
        close_agent_session,
        name="close_agent_session",
        description="Close an agent session binding and optionally announce it.",
        title="Close agent session",
    )

    # Files
    register_tool(
        mcp,
        upload_file,
        name="upload_file",
        description="Upload a file to Zulip and get a link to share.",
        title="Upload file",
    )
    register_tool(
        mcp,
        manage_files,
        name="manage_files",
        description="List, delete, share, or download your Zulip uploads.",
        title="Manage files",
        destructive=True,
    )
    register_tool(
        mcp,
        update_message_flags_for_narrow,
        name="update_message_flags_for_narrow",
        description="Set or clear a flag on every Zulip message in a narrow.",
        title="Update message flags for narrow",
        idempotent=True,
    )
