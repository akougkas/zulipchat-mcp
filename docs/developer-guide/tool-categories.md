# Tool Categories

## Core mode (19 tools)

### Messaging and reactions (4)

- `send_message`
- `edit_message`
- `get_message`
- `add_reaction`

### Search and discovery (4)

- `search_messages`
- `get_streams`
- `get_stream_info`
- `get_stream_topics`

### Users (3)

- `resolve_user`
- `get_users`
- `get_own_user`

### Agent communication (5)

- `teleport_chat`
- `register_agent`
- `agent_message`
- `request_user_input`
- `wait_for_response`

### System and flags (3)

- `switch_identity`
- `server_info`
- `manage_message_flags`

## Extended additions (36 tools)

### Users and presence

- `get_user`, `get_user_status`, `update_status`
- `get_user_presence`, `get_presence`
- `get_user_groups`, `get_user_group_members`, `is_user_group_member`
- `manage_user_mute`

### Messaging and search

- `cross_post_message`, `toggle_reaction`
- `advanced_search`, `construct_narrow`, `check_messages_match_narrow`

### Scheduled messages

- `get_scheduled_messages`, `manage_scheduled_message`

### Events

- `register_events`, `get_events`, `listen_events`, `deregister_events`

### AI analytics

- `get_daily_summary`
- `analyze_stream_with_llm`
- `analyze_team_activity_with_llm`
- `intelligent_report_generator`

### Agent extensions

- `send_agent_status`, `manage_task`, `list_instances`
- `afk_mode`, `poll_agent_events`

### Files and topics

- `upload_file`, `manage_files`
- `agents_channel_topic_ops`

### Command chains and raw flags

- `execute_chain`, `list_command_types`
- `update_message_flags_for_narrow`

## Design intent

- Keep common workflows on a compact default registry.
- Move heavier or specialized operations to explicit extended mode.
