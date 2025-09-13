"""Tool parameter schemas for all v2.5.0 ZulipChat MCP tools."""

from __future__ import annotations

from .types import ParameterSchema, ToolSchema


def get_messaging_schemas() -> dict[str, ToolSchema]:
    """Get parameter schemas for messaging tools."""
    return {
        "messaging.message": ToolSchema(
            name="messaging.message",
            description="Send, schedule, or draft messages",
            parameters=[
                ParameterSchema(
                    name="operation",
                    type="str",
                    description="Operation type (send/schedule/draft)",
                    required=True,
                    basic_param=True,
                    choices=["send", "schedule", "draft"],
                ),
                ParameterSchema(
                    name="type",
                    type="str",
                    description="Message type (stream/private)",
                    required=True,
                    basic_param=True,
                    choices=["stream", "private"],
                ),
                ParameterSchema(
                    name="to",
                    type="str|list",
                    description="Recipient(s)",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="content",
                    type="str",
                    description="Message content",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="topic",
                    type="str",
                    description="Topic for stream messages",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="schedule_at",
                    type="datetime",
                    description="Schedule time",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="queue_id",
                    type="str",
                    description="Queue ID for sending",
                    expert_param=True,
                ),
                ParameterSchema(
                    name="local_id",
                    type="str",
                    description="Local message ID",
                    expert_param=True,
                ),
                ParameterSchema(
                    name="read_by_sender",
                    type="bool",
                    description="Mark as read by sender",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="syntax_highlight",
                    type="bool",
                    description="Enable syntax highlighting",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="link_preview",
                    type="bool",
                    description="Enable link previews",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="emoji_translate",
                    type="bool",
                    description="Enable emoji translation",
                    default=True,
                    advanced_param=True,
                ),
            ],
        ),
        "messaging.search_messages": ToolSchema(
            name="messaging.search_messages",
            description="Search and retrieve messages",
            parameters=[
                ParameterSchema(
                    name="narrow",
                    type="list",
                    description="Message filters",
                    default=[],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="anchor",
                    type="str|int",
                    description="Anchor message ID",
                    default="newest",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="num_before",
                    type="int",
                    description="Messages before anchor",
                    default=50,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="num_after",
                    type="int",
                    description="Messages after anchor",
                    default=50,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="include_anchor",
                    type="bool",
                    description="Include anchor message",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="use_first_unread_anchor",
                    type="bool",
                    description="Use first unread as anchor",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="apply_markdown",
                    type="bool",
                    description="Apply markdown formatting",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="client_gravatar",
                    type="bool",
                    description="Include gravatar URLs",
                    default=False,
                    advanced_param=True,
                ),
            ],
        ),
        "messaging.edit_message": ToolSchema(
            name="messaging.edit_message",
            description="Edit or move messages with topic management",
            parameters=[
                ParameterSchema(
                    name="message_id",
                    type="int",
                    description="ID of message to edit",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="content",
                    type="str",
                    description="New message content",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="topic",
                    type="str",
                    description="New topic name",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="stream_id",
                    type="int",
                    description="Move to different stream",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="propagate_mode",
                    type="str",
                    description="Topic propagation control",
                    default="change_one",
                    choices=["change_one", "change_later", "change_all"],
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="send_notification_to_old_thread",
                    type="bool",
                    description="Notify old thread",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="send_notification_to_new_thread",
                    type="bool",
                    description="Notify new thread",
                    default=True,
                    advanced_param=True,
                ),
            ],
        ),
        "messaging.bulk_operations": ToolSchema(
            name="messaging.bulk_operations",
            description="Bulk message operations",
            parameters=[
                ParameterSchema(
                    name="operation",
                    type="str",
                    description="Bulk operation type",
                    required=True,
                    choices=["mark_read", "mark_unread", "add_flag", "remove_flag"],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="narrow",
                    type="list",
                    description="Message filters for selection",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="message_ids",
                    type="list",
                    description="Specific message IDs",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="flag",
                    type="str",
                    description="Flag name for flag operations",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="batch_size",
                    type="int",
                    description="Processing batch size",
                    default=100,
                    min_value=1,
                    max_value=1000,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="timeout",
                    type="int",
                    description="Operation timeout in seconds",
                    default=30,
                    min_value=1,
                    max_value=300,
                    expert_param=True,
                ),
            ],
        ),
    }


def get_streams_schemas() -> dict[str, ToolSchema]:
    """Get parameter schemas for stream management tools."""
    return {
        "streams.manage_streams": ToolSchema(
            name="streams.manage_streams",
            description="Manage streams with bulk operations support",
            parameters=[
                ParameterSchema(
                    name="operation",
                    type="str",
                    description="Stream operation type",
                    required=True,
                    choices=[
                        "list",
                        "create",
                        "update",
                        "delete",
                        "subscribe",
                        "unsubscribe",
                    ],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="stream_ids",
                    type="list",
                    description="Stream IDs for bulk operations",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="stream_names",
                    type="list",
                    description="Stream names for operations",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="name",
                    type="str",
                    description="Stream name for single operations",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="description",
                    type="str",
                    description="Stream description",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="invite_only",
                    type="bool",
                    description="Private stream",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="announce",
                    type="bool",
                    description="Announce creation",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="principals",
                    type="list",
                    description="Users to also subscribe",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_public",
                    type="bool",
                    description="Include public streams",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_subscribed",
                    type="bool",
                    description="Include subscribed streams",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_all_active",
                    type="bool",
                    description="Include all active streams",
                    default=False,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="stream_post_policy",
                    type="int",
                    description="Who can post policy",
                    default=1,
                    min_value=1,
                    max_value=4,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="history_public_to_subscribers",
                    type="bool",
                    description="History visibility",
                    default=True,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="message_retention_days",
                    type="int",
                    description="Message retention",
                    min_value=1,
                    expert_param=True,
                ),
            ],
        ),
        "streams.manage_topics": ToolSchema(
            name="streams.manage_topics",
            description="Bulk topic operations within streams",
            parameters=[
                ParameterSchema(
                    name="stream_id",
                    type="int",
                    description="Stream ID for topic operations",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="operation",
                    type="str",
                    description="Topic operation type",
                    required=True,
                    choices=["list", "move", "delete", "mark_read", "mute", "unmute"],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="source_topic",
                    type="str",
                    description="Source topic name",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="target_topic",
                    type="str",
                    description="Target topic name",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="target_stream_id",
                    type="int",
                    description="Target stream for moves",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="propagate_mode",
                    type="str",
                    description="Topic propagation control",
                    default="change_all",
                    choices=["change_one", "change_later", "change_all"],
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_muted",
                    type="bool",
                    description="Include muted topics",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="max_results",
                    type="int",
                    description="Maximum results",
                    default=100,
                    min_value=1,
                    max_value=1000,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="send_notifications",
                    type="bool",
                    description="Send move notifications",
                    default=True,
                    expert_param=True,
                ),
            ],
        ),
        "streams.get_stream_info": ToolSchema(
            name="streams.get_stream_info",
            description="Get comprehensive stream information",
            parameters=[
                ParameterSchema(
                    name="stream_id",
                    type="int",
                    description="Stream ID to get info for",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="stream_name",
                    type="str",
                    description="Stream name to get info for",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="include_topics",
                    type="bool",
                    description="Include topic list",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_subscribers",
                    type="bool",
                    description="Include subscriber list",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_settings",
                    type="bool",
                    description="Include stream settings",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="topic_limit",
                    type="int",
                    description="Max topics to return",
                    default=50,
                    min_value=1,
                    max_value=500,
                    advanced_param=True,
                ),
            ],
        ),
    }


def get_events_schemas() -> dict[str, ToolSchema]:
    """Get parameter schemas for event streaming tools."""
    return {
        "events.register_events": ToolSchema(
            name="events.register_events",
            description="Register for real-time events without persistence",
            parameters=[
                ParameterSchema(
                    name="event_types",
                    type="list",
                    description="List of event types to monitor",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="narrow",
                    type="list",
                    description="Event filters",
                    default=[],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="all_public_streams",
                    type="bool",
                    description="Monitor all public streams",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="queue_lifespan_secs",
                    type="int",
                    description="Queue auto-cleanup time",
                    default=300,
                    min_value=60,
                    max_value=3600,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="fetch_event_types",
                    type="list",
                    description="Initial state event types",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="client_capabilities",
                    type="dict",
                    description="Client capability declaration",
                    expert_param=True,
                ),
                ParameterSchema(
                    name="include_subscribers",
                    type="bool",
                    description="Include subscriber data",
                    default=False,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="slim_presence",
                    type="bool",
                    description="Slim presence format",
                    default=True,
                    expert_param=True,
                ),
            ],
        ),
        "events.get_events": ToolSchema(
            name="events.get_events",
            description="Poll events from queue (stateless)",
            parameters=[
                ParameterSchema(
                    name="queue_id",
                    type="str",
                    description="Event queue ID",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="last_event_id",
                    type="int",
                    description="Last processed event ID",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="dont_block",
                    type="bool",
                    description="Disable long-polling",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="timeout",
                    type="int",
                    description="Long-polling timeout",
                    default=10,
                    min_value=1,
                    max_value=60,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="max_events",
                    type="int",
                    description="Maximum events per request",
                    default=100,
                    min_value=1,
                    max_value=1000,
                    expert_param=True,
                ),
            ],
        ),
        "events.listen_events": ToolSchema(
            name="events.listen_events",
            description="Simple event listener with callback support",
            parameters=[
                ParameterSchema(
                    name="event_types",
                    type="list",
                    description="List of event types to monitor",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="callback_url",
                    type="str",
                    description="Webhook URL for events",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="filters",
                    type="dict",
                    description="Event filters",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="duration",
                    type="int",
                    description="Listen duration in seconds",
                    default=300,
                    min_value=60,
                    max_value=3600,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="retry_on_error",
                    type="bool",
                    description="Auto-retry on errors",
                    default=True,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="error_threshold",
                    type="int",
                    description="Max consecutive errors",
                    default=5,
                    min_value=1,
                    max_value=50,
                    expert_param=True,
                ),
            ],
        ),
    }


def get_users_schemas() -> dict[str, ToolSchema]:
    """Get parameter schemas for user management tools."""
    return {
        "users.manage_users": ToolSchema(
            name="users.manage_users",
            description="User operations with identity context",
            parameters=[
                ParameterSchema(
                    name="operation",
                    type="str",
                    description="User operation type",
                    required=True,
                    choices=["list", "get", "update", "presence", "groups"],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="user_id",
                    type="int",
                    description="User ID for operations",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="email",
                    type="str",
                    description="User email for operations",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="as_bot",
                    type="bool",
                    description="Use bot identity",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="as_admin",
                    type="bool",
                    description="Requires admin credentials",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="full_name",
                    type="str",
                    description="Updated full name",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="status_text",
                    type="str",
                    description="User status text",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="status_emoji",
                    type="str",
                    description="User status emoji",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="status",
                    type="str",
                    description="Presence status",
                    choices=["active", "idle", "offline"],
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="client",
                    type="str",
                    description="Client name for presence",
                    default="MCP",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_custom_profile_fields",
                    type="bool",
                    description="Include custom fields",
                    default=False,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="client_gravatar",
                    type="bool",
                    description="Include gravatar URLs",
                    default=True,
                    expert_param=True,
                ),
            ],
        ),
        "users.switch_identity": ToolSchema(
            name="users.switch_identity",
            description="Switch identity context for operations",
            parameters=[
                ParameterSchema(
                    name="identity",
                    type="str",
                    description="Identity type to switch to",
                    required=True,
                    choices=["user", "bot", "admin"],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="persist",
                    type="bool",
                    description="Make switch permanent for session",
                    default=False,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="validate",
                    type="bool",
                    description="Validate credentials before switch",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="timeout",
                    type="int",
                    description="Validation timeout",
                    default=10,
                    min_value=1,
                    max_value=60,
                    expert_param=True,
                ),
            ],
        ),
        "users.manage_user_groups": ToolSchema(
            name="users.manage_user_groups",
            description="Manage user groups and permissions",
            parameters=[
                ParameterSchema(
                    name="action",
                    type="str",
                    description="Group action",
                    required=True,
                    choices=[
                        "create",
                        "update",
                        "delete",
                        "add_members",
                        "remove_members",
                    ],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="group_name",
                    type="str",
                    description="Group name",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="group_id",
                    type="int",
                    description="Group ID",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="description",
                    type="str",
                    description="Group description",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="members",
                    type="list",
                    description="Member user IDs",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="can_mention_group",
                    type="str",
                    description="Who can mention this group",
                    choices=["everyone", "members", "nobody"],
                    expert_param=True,
                ),
            ],
        ),
    }


def get_search_schemas() -> dict[str, ToolSchema]:
    """Get parameter schemas for search and analytics tools."""
    return {
        "search.advanced_search": ToolSchema(
            name="search.advanced_search",
            description="Multi-faceted search across Zulip",
            parameters=[
                ParameterSchema(
                    name="query",
                    type="str",
                    description="Search query string",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="search_type",
                    type="list",
                    description="Search target types",
                    default=["messages"],
                    choices=["messages", "users", "streams", "topics"],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="narrow",
                    type="list",
                    description="Search filters",
                    default=[],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="highlight",
                    type="bool",
                    description="Highlight search terms",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="aggregations",
                    type="list",
                    description="Result aggregations",
                    choices=["sender", "stream", "topic", "day", "hour"],
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="time_range",
                    type="dict",
                    description="Time range filter",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="sort_by",
                    type="str",
                    description="Sort order",
                    default="relevance",
                    choices=["newest", "oldest", "relevance"],
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="limit",
                    type="int",
                    description="Maximum results",
                    default=100,
                    min_value=1,
                    max_value=1000,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="use_cache",
                    type="bool",
                    description="Use search cache",
                    default=True,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="timeout",
                    type="int",
                    description="Search timeout",
                    default=30,
                    min_value=1,
                    max_value=120,
                    expert_param=True,
                ),
            ],
        ),
        "search.analytics": ToolSchema(
            name="search.analytics",
            description="Analytics and insights from message data",
            parameters=[
                ParameterSchema(
                    name="metric",
                    type="str",
                    description="Analytics metric",
                    required=True,
                    choices=["activity", "sentiment", "topics", "participation"],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="narrow",
                    type="list",
                    description="Data filters",
                    default=[],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="group_by",
                    type="str",
                    description="Grouping dimension",
                    choices=["user", "stream", "day", "hour"],
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="time_range",
                    type="dict",
                    description="Time range for analysis",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="format",
                    type="str",
                    description="Output format",
                    default="summary",
                    choices=["summary", "detailed", "chart_data"],
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_stats",
                    type="bool",
                    description="Include statistical summary",
                    default=True,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="min_activity_threshold",
                    type="int",
                    description="Minimum activity for inclusion",
                    default=1,
                    min_value=1,
                    expert_param=True,
                ),
            ],
        ),
    }


def get_files_schemas() -> dict[str, ToolSchema]:
    """Get parameter schemas for file management tools."""
    return {
        "files.upload_file": ToolSchema(
            name="files.upload_file",
            description="Upload files with progress tracking",
            parameters=[
                ParameterSchema(
                    name="file_path",
                    type="str",
                    description="Local file path to upload",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="file_content",
                    type="bytes",
                    description="File content as bytes",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="filename",
                    type="str",
                    description="Target filename",
                    required=True,
                    basic_param=True,
                ),
                ParameterSchema(
                    name="stream",
                    type="str",
                    description="Auto-share to stream",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="topic",
                    type="str",
                    description="Topic for auto-share",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="message",
                    type="str",
                    description="Accompanying message",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="chunk_size",
                    type="int",
                    description="Upload chunk size",
                    default=1048576,
                    min_value=1024,
                    max_value=10485760,
                    expert_param=True,
                ),
                ParameterSchema(
                    name="mime_type",
                    type="str",
                    description="MIME type override",
                    expert_param=True,
                ),
                ParameterSchema(
                    name="progress_callback",
                    type="str",
                    description="Progress callback URL",
                    expert_param=True,
                ),
            ],
        ),
        "files.manage_files": ToolSchema(
            name="files.manage_files",
            description="Manage uploaded files and attachments",
            parameters=[
                ParameterSchema(
                    name="operation",
                    type="str",
                    description="File operation",
                    required=True,
                    choices=["list", "get", "delete", "share", "download"],
                    basic_param=True,
                ),
                ParameterSchema(
                    name="file_id",
                    type="str",
                    description="File ID for operations",
                    basic_param=True,
                ),
                ParameterSchema(
                    name="filters",
                    type="dict",
                    description="File filters for listing",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="download_path",
                    type="str",
                    description="Local download path",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="share_in_stream",
                    type="str",
                    description="Stream to share file in",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="share_in_topic",
                    type="str",
                    description="Topic to share file in",
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="limit",
                    type="int",
                    description="Maximum files to list",
                    default=100,
                    min_value=1,
                    max_value=1000,
                    advanced_param=True,
                ),
                ParameterSchema(
                    name="include_metadata",
                    type="bool",
                    description="Include file metadata",
                    default=True,
                    expert_param=True,
                ),
            ],
        ),
    }


def get_all_schemas() -> dict[str, ToolSchema]:
    """Get all tool parameter schemas."""
    schemas = {}
    schemas.update(get_messaging_schemas())
    schemas.update(get_streams_schemas())
    schemas.update(get_events_schemas())
    schemas.update(get_users_schemas())
    schemas.update(get_search_schemas())
    schemas.update(get_files_schemas())

    return schemas
