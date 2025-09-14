# 📊 Complete ZulipChat MCP v2.5.1 Tool Implementation Analysis

  Based on exhaustive examination of all implementation files, here are ALL 43 tools with their complete specifications:

## Messaging Tools (7 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `send_message` | `type: Literal["stream", "private"]`<br>`to: str \| list[str]`<br>`content: str`<br>`topic: str \| None`<br>`schedule_at: datetime \| None` | Send or schedule messages | Core Zulip functionality - Essential for any Zulip interaction. Supports both immediate and scheduled messaging via Zulip's native API. |
| `edit_message` | `message_id: int`<br>`content: str \| None`<br>`topic: str \| None`<br>`stream_id: int \| None`<br>`propagate_mode: Literal["change_one", "change_later", "change_all"]` | Edit message content, topic, or move between streams | Content management - Allows post-send corrections and organization. Propagation modes enable bulk topic changes and stream migrations. |
| `add_reaction` | `message_id: int`<br>`emoji_name: str` | Add emoji reaction to message | Social engagement - Enables quick feedback and acknowledgment without full messages. Critical for team communication dynamics. |
| `remove_reaction` | `message_id: int`<br>`emoji_name: str` | Remove emoji reaction from message | Reaction management - Allows correction of accidental reactions or changed opinions. Maintains clean communication history. |
| `bulk_operations` | `operation: Literal[...]`<br>`message_ids: list[int] \| None`<br>`stream: str \| None`<br>`topic: str \| None`<br>`sender: str \| None`<br>`flag: str \| None`<br>`emoji_name: str \| None` | Perform bulk operations on multiple messages | Efficiency tool - Essential for managing large conversations. Enables mass read/unread, flagging, and reaction management for productivity. |
| `message_history` | `message_id: int` | Get message history with edits and reactions | Audit trail - Provides transparency and tracking for edited messages. Critical for understanding conversation evolution and accountability. |
| `cross_post_message` | `source_message_id: int`<br>`target_streams: list[str]`<br>`target_topic: str \| None`<br>`add_reference: bool`<br>`custom_prefix: str \| None` | Cross-post message to multiple streams | Information distribution - Enables sharing important messages across relevant teams. Attribution prevents confusion about message origins. |

## Search & Analytics Tools (5 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `search_messages` | `query: str \| None`<br>`stream: str \| None`<br>`topic: str \| None`<br>`sender: str \| None`<br>`has_attachment: bool \| None`<br>`has_link: bool \| None`<br>`has_image: bool \| None`<br>`is_private: bool \| None`<br>`is_starred: bool \| None`<br>`is_mentioned: bool \| None`<br>`last_hours: int \| str \| None`<br>`last_days: int \| str \| None`<br>`after_time: datetime \| str \| None`<br>`before_time: datetime \| str \| None`<br>`limit: int`<br>`sort_by: Literal[...]`<br>`highlight: bool` | Advanced search with fuzzy user matching and comprehensive filtering | Information retrieval - Core knowledge management tool. Fuzzy user matching solves the "Jaime" → email problem. Comprehensive filters enable precise data extraction. |
| `advanced_search` | `query: str`<br>`search_type: list[Literal[...]] \| None`<br>`stream: str \| None`<br>`topic: str \| None`<br>`sender: str \| None`<br>`has_attachment: bool \| None`<br>`has_link: bool \| None`<br>`is_private: bool \| None`<br>`is_starred: bool \| None`<br>`last_hours: int \| None`<br>`last_days: int \| None`<br>`limit: int`<br>`sort_by: Literal[...]`<br>`highlight: bool`<br>`aggregations: list[str] \| None` | Multi-faceted search across messages, users, streams with aggregations | Data discovery - Enables searching across all Zulip entities simultaneously. Aggregations provide statistical insights for organizational understanding. |
| `analytics` | `metric: Literal["activity", "sentiment", "topics", "participation"]`<br>`stream: str \| None`<br>`sender: str \| None`<br>`last_hours: int \| None`<br>`last_days: int \| None`<br>`format: Literal[...]`<br>`group_by: Literal[...] \| None` | Generate analytics and insights from message data | Team intelligence - Provides data-driven insights for team management. Basic analytics enable trend identification and team health monitoring. |
| `get_daily_summary` | `streams: list[str] \| None`<br>`hours_back: int` | Get daily activity summary with engagement metrics | Status reporting - Daily operational intelligence for managers and team leads. Quick overview of organizational activity patterns. |
| `analyze_with_llm` | `data_source: Literal["messages", "streams", "users"]`<br>`analysis_type: str`<br>`stream: str \| None`<br>`topic: str \| None`<br>`sender: str \| None`<br>`last_hours: int \| None`<br>`last_days: int \| None`<br>`limit: int`<br>`custom_prompt: str \| None`<br>`ctx: Any` | Fetch Zulip data and analyze with LLM via elicitation | AI-powered insights - KEY INNOVATION - Uses FastMCP elicitation to enable sophisticated analysis. LLM processes Zulip data for custom insights without server complexity. |

## Stream & Topic Management Tools (5 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `manage_streams` | `operation: Literal[...]`<br>`stream_names: list[str] \| None`<br>`stream_ids: list[int] \| None`<br>`properties: dict[str, Any] \| None`<br>`principals: list[str] \| None`<br>`announce: bool`<br>`invite_only: bool`<br>`include_public: bool`<br>`include_subscribed: bool`<br>`include_all_active: bool`<br>`authorization_errors_fatal: bool`<br>`history_public_to_subscribers: bool \| None`<br>`stream_post_policy: int \| None`<br>`message_retention_days: int \| None` | Complete stream lifecycle management with bulk operations | Organizational structure - Core Zulip administration. Bulk operations enable efficient team onboarding and stream management at scale. |
| `manage_topics` | `stream_id: int`<br>`operation: Literal[...]`<br>`source_topic: str \| None`<br>`target_topic: str \| None`<br>`target_stream_id: int \| None`<br>`propagate_mode: str`<br>`send_notification_to_new_thread: bool`<br>`send_notification_to_old_thread: bool`<br>`max_results: int`<br>`include_muted: bool` | Topic operations within streams including move, delete, mute | Content organization - Topics are Zulip's unique threading system. Management tools enable conversation organization and housekeeping. |
| `get_stream_info` | `stream_name: str \| None`<br>`stream_id: int \| None`<br>`include_subscribers: bool`<br>`include_topics: bool`<br>`include_settings: bool`<br>`include_web_public: bool` | Get comprehensive stream information with analytics | Inspection tool - Provides detailed stream metadata for decision-making. Optional inclusions prevent unnecessary API calls. |
| `stream_analytics` | `stream_name: str \| None`<br>`stream_id: int \| None`<br>`time_period: Literal[...]`<br>`include_message_stats: bool`<br>`include_topic_stats: bool`<br>`include_user_activity: bool` | Generate detailed stream statistics and analytics | Performance monitoring - Stream-specific insights for community management. Identifies engagement patterns and community health indicators. |
| `manage_stream_settings` | `stream_id: int`<br>`operation: Literal[...]`<br>`color: str \| None`<br>`pin_to_top: bool \| None`<br>`notification_settings: dict[str, Any] \| None`<br>`permission_updates: dict[str, Any] \| None` | Manage personal stream notification preferences and settings | User experience - Personalizes Zulip interface. Essential for notification management and workspace organization. |

## User Management Tools (13 tools) - READ-ONLY Based on Zulip API

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `get_users` | `client_gravatar: bool`<br>`include_custom_profile_fields: bool`<br>`user_ids: list[int] \| None` | Get all users in organization | Directory service - Core organizational awareness. Essential for user discovery and team mapping. |
| `get_user_by_id` | `user_id: int`<br>`client_gravatar: bool`<br>`include_custom_profile_fields: bool` | Get specific user by ID | User lookup - Direct user information retrieval when ID is known. Efficient for programmatic access. |
| `get_user_by_email` | `email: str`<br>`client_gravatar: bool`<br>`include_custom_profile_fields: bool` | Get specific user by email | User resolution - Most common user identification method. Email-based lookup for human-friendly queries. |
| `get_own_user` | None | Get information about current user | Self-awareness - Allows tools to understand their own identity and permissions. Essential for context-aware operations. |
| `get_user_status` | `user_id: int` | Get user's status text and emoji | Presence awareness - Modern status information including custom text and emoji. Enables context-sensitive communication. |
| `update_status` | `status_text: str \| None`<br>`emoji_name: str \| None`<br>`emoji_code: str \| None`<br>`reaction_type: Literal[...]` | Update your own status text and emoji | Status management - Personal status control. Essential for communicating availability and context to team members. |
| `get_user_presence` | `user_id_or_email: str \| int` | Get presence information for specific user | Individual presence - Detailed presence data for specific users. Enables smart message timing and availability awareness. |
| `get_presence` | None | Get presence information for all users | Team awareness - Organization-wide presence overview. Critical for understanding team availability patterns and optimal communication timing. |
| `get_user_groups` | `include_deactivated_groups: bool` | Get all user groups in organization | Group discovery - Organizational structure awareness. Essential for understanding team hierarchies and communication patterns. |
| `get_user_group_members` | `user_group_id: int`<br>`direct_member_only: bool` | Get members of specific user group | Group composition - Detailed group membership information. Enables targeted communication and permission understanding. |
| `is_user_group_member` | `user_group_id: int`<br>`user_id: int`<br>`direct_member_only: bool` | Check if user is member of user group | Membership verification - Precise group membership testing. Essential for permission-aware operations and access control. |
| `mute_user` | `muted_user_id: int` | Mute a user for your own notifications | Notification control - Personal noise management. Critical for productivity in high-traffic organizations. |
| `unmute_user` | `muted_user_id: int` | Unmute a user for your own notifications | Notification restoration - Reverses muting when communication is needed again. Maintains relationship management. |

## Event System Tools (4 core + 5 agent = 9 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `register_events` | `event_types: list[str]`<br>`narrow: list[dict[str, Any]] \| None`<br>`queue_lifespan_secs: int`<br>`all_public_streams: bool`<br>`include_subscribers: bool`<br>`client_gravatar: bool`<br>`slim_presence: bool`<br>`fetch_event_types: list[str] \| None`<br>`client_capabilities: dict[str, Any] \| None` | Register for comprehensive real-time event streams | Real-time foundation - Core event system setup. Enables reactive programming patterns and live updates. Comprehensive parameters support all Zulip event types. |
| `get_events` | `queue_id: str`<br>`last_event_id: int`<br>`dont_block: bool`<br>`timeout: int`<br>`apply_markdown: bool`<br>`client_gravatar: bool`<br>`user_client: str \| None` | Poll events from registered queue with long-polling | Event consumption - Retrieves real-time events efficiently. Long-polling reduces server load while maintaining responsiveness. |
| `listen_events` | `event_types: list[str]`<br>`duration: int`<br>`narrow: list[dict[str, Any]] \| None`<br>`filters: dict[str, Any] \| None`<br>`poll_interval: int`<br>`max_events_per_poll: int`<br>`all_public_streams: bool`<br>`callback_url: str \| None` | Comprehensive stateless event listener with webhook integration | Autonomous monitoring - Self-contained event processing with webhook support. Enables external system integration and automation. |
| `deregister_events` | `queue_id: str` | Deregister event queue | Resource cleanup - Proper queue lifecycle management. Prevents resource leaks in long-running applications. |
| `register_agent` | `agent_type: str` | Register AI agent instance and create database records | Agent initialization - Sets up agent identity and tracking. Essential for multi-agent coordination and session management. |
| `agent_message` | `content: str`<br>`require_response: bool`<br>`agent_type: str` | Send bot-authored messages via Agents-Channel | Agent communication - Enables AI agents to communicate back to users. AFK-gated to prevent spam. Uses dedicated channel for organization. |
| `enable_afk_mode` | `hours: int`<br>`reason: str` | Enable AFK mode for automatic notifications | Presence automation - Activates agent communication when user is away. Enables autonomous AI assistant operation during absence. |
| `disable_afk_mode` | None | Disable AFK mode and restore normal operation | Presence restoration - Returns to normal operation mode. Prevents notification spam when user is present. |
| `get_afk_status` | None | Query current AFK mode status | Status awareness - Allows tools to understand current operational mode. Essential for context-aware behavior. |

## File Management Tools (2 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `upload_file` | `file_content: bytes \| None`<br>`file_path: str \| None`<br>`filename: str`<br>`mime_type: str \| None`<br>`chunk_size: int`<br>`stream: str \| None`<br>`topic: str \| None`<br>`message: str \| None` | Upload files with comprehensive security validation and sharing | Content delivery - Secure file upload with automatic sharing. Security validation prevents malicious uploads. Auto-sharing enables seamless workflow integration. |
| `manage_files` | `operation: Literal[...]`<br>`file_id: str \| None`<br>`filters: dict[str, Any] \| None`<br>`download_path: str \| None`<br>`share_in_stream: str \| None`<br>`share_in_topic: str \| None` | File management operations with Zulip API limitations | File lifecycle - Comprehensive file operations within Zulip's API constraints. Transparent about limitations while providing maximum possible functionality. |

## System Tools (2 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `switch_identity` | `identity: Literal["user", "bot"]` | Switch between user and bot identities | Identity management - Core dual-identity system. Enables context-appropriate permissions and prevents unauthorized operations. |
| `server_info` | None | Get server information and capabilities | Server discovery - Provides metadata about available features and current configuration. Essential for client capability negotiation. |

## Agent Communication Tools (13 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `register_agent` | `agent_type: str` | Register AI agent instance and create database records | Agent lifecycle - Initializes agent tracking and communication capabilities. Creates persistent identity for session continuity. |
| `agent_message` | `content: str`<br>`require_response: bool`<br>`agent_type: str` | Send bot-authored messages via Agents-Channel | Bot communication - Dedicated agent-to-user messaging. Respects AFK mode to prevent spam. Uses structured topics for organization. |
| `wait_for_response` | `request_id: str` | Wait for user response with timeout-based polling | Synchronous interaction - Enables interactive workflows between agents and users. Timeout prevents hanging operations. |
| `send_agent_status` | `agent_type: str`<br>`status: str`<br>`message: str` | Set and track agent status updates | Status broadcasting - Allows agents to communicate their operational state. Essential for multi-agent coordination. |
| `request_user_input` | `agent_id: str`<br>`question: str`<br>`options: list[str] \| None`<br>`context: str` | Request interactive user input with intelligent routing | Interactive workflows - Enables AI agents to ask users for clarification or decisions. Smart routing ensures messages reach the right person. |
| `start_task` | `agent_id: str`<br>`name: str`<br>`description: str` | Initialize task tracking with database persistence | Task management - Begins task lifecycle tracking. Enables progress monitoring and accountability for long-running operations. |
| `update_task_progress` | `task_id: str`<br>`progress: int`<br>`status: str` | Update task progress with percentage and status tracking | Progress reporting - Real-time task status updates. Enables monitoring of long-running operations and workflow visibility. |
| `complete_task` | `task_id: str`<br>`outputs: str`<br>`metrics: str` | Finalize task completion with results tracking | Task closure - Completes task lifecycle with results documentation. Enables outcome tracking and performance analysis. |
| `list_instances` | None | Retrieve all agent instances with session details | Agent discovery - Multi-agent coordination support. Enables understanding of active agents and their contexts. |
| `enable_afk_mode` | `hours: int`<br>`reason: str` | Enable AFK mode for automatic notifications | Automation activation - Enables agent operation during user absence. Critical for autonomous AI assistant functionality. |
| `disable_afk_mode` | None | Disable AFK mode and restore normal operation | Automation deactivation - Returns to manual operation mode. Prevents unwanted notifications when user returns. |
| `get_afk_status` | None | Query current AFK mode status | Status inquiry - Allows checking current operational mode. Essential for context-aware agent behavior. |
| `poll_agent_events` | `limit: int`<br>`topic_prefix: str \| None` | Poll unacknowledged chat events with topic filtering | Event processing - Retrieves user messages for agent processing. Enables asynchronous agent-user communication. |

## Command Automation Tools (2 tools)

| Tool | Arguments | Description | Justification |
|------|-----------|-------------|---------------|
| `execute_chain` | `commands: list[dict]` | Execute sophisticated command chains for workflow automation | Workflow orchestration - Enables complex multi-step operations with conditional logic. Critical for automation and advanced use cases. |
| `list_command_types` | None | List all available command types for workflow construction | Workflow discovery - Provides metadata about available command types. Essential for building complex automation workflows. |

## Integration Features (3 client-side commands)

| Integration | Arguments | Description | Justification |
|-------------|-----------|-------------|---------------|
| `zulip-daily-summary` | Tool chain: `search_messages` + `get_daily_summary` | Claude Code command for daily summary | Client convenience - Pre-built workflow for common use case. Reduces complexity for end users while leveraging core tools. |
| `zulip-morning-briefing` | Tool chain: `get_daily_summary` with specific streams | Claude Code command for morning briefing | Morning routine - Automated morning update workflow. Provides consistent team awareness without manual queries. |
| `zulip-catch-up` | Tool chain: `get_daily_summary` with 4-hour window | Claude Code command for quick catch-up | Quick updates - Short-term activity overview. Enables rapid context acquisition after brief absences. |

---

## 🎯 Total: 43 Tools + 3 Integration Commands = 46 Total Features

### Key Architectural Principles Verified:

1. **Simple Tools, Sophisticated Outcomes** - Each tool does one thing well, but complex use cases emerge from LLM reasoning and tool combinations
2. **LLM Elicitation Over Built-in Complexity** - `analyze_with_llm` uses FastMCP elicitation to enable AI-powered insights without server complexity
3. **READ-ONLY User Management** - No user creation/editing, just discovery and information retrieval based on Zulip API reality
4. **Optional Complexity** - Agent features gracefully degrade when database unavailable
5. **Clean Abstractions** - Each tool maps directly to Zulip API capabilities without unnecessary layers