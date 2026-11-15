# Tool Categories

The registry lives in `src/zulipchat_mcp/tools/__init__.py`: `CORE_TOOLS` and
`register_core_tools` for the default surface, `register_extended_tools` for
the rest. Profiles in `src/zulipchat_mcp/core/tool_contract.py` narrow either
surface.

## Core mode (21 tools)

### Messaging and reactions (5)

- `send_message`
- `edit_message`
- `get_message`
- `add_reaction`
- `manage_message_flags`

### Bot inbox (3)

- `wait_for_mentions`
- `reply`
- `teleport_chat`

### Search and discovery (5)

- `search_messages`
- `get_streams`
- `get_stream_topics`
- `resolve_user`
- `get_users`

### Agent sessions (6)

- `register_agent`
- `ensure_agent_session`
- `agent_message`
- `request_user_input`
- `wait_for_response`
- `poll_agent_events`

### System (2)

- `server_info`
- `switch_identity`

## Extended additions (34 tools, 55 total)

### Users and presence (10)

- `get_own_user`, `get_user`, `get_user_status`, `update_status`
- `get_user_presence`, `get_presence`
- `get_user_groups`, `get_user_group_members`
- `manage_user_mute`, `set_typing`

### Channels and topics (3)

- `get_stream_info`, `resolve_topic`, `set_topic_visibility`

### Messages (6)

- `cross_post_message`, `get_read_receipts`, `get_message_history`
- `check_messages_match_narrow`, `update_message_flags_for_narrow`
- `get_daily_summary`

### Scheduled messages, reminders and drafts (7)

- `get_scheduled_messages`, `manage_scheduled_message`, `manage_reminders`
- `get_drafts`, `create_draft`, `edit_draft`, `delete_draft`

### Events (4)

- `register_events`, `get_events`, `listen_events`, `deregister_events`

### Agent sessions (2)

- `list_sessions`, `close_agent_session`

### Files (2)

- `upload_file`, `manage_files`

## Tool profiles

| Profile | Core | Extended |
| --- | --- | --- |
| `full` | 21 | 55 |
| `read-only` | 7 | 22 |
| `bot` | 9 | 9 |

`read-only` keeps `READ_ONLY_TOOLS`: `server_info`, `get_message`,
`search_messages`, `get_streams`, `get_stream_topics`, `resolve_user` and
`get_users` in core, plus `get_stream_info`, `get_own_user`, `get_user`,
`get_user_status`, `get_user_presence`, `get_presence`, `get_user_groups`,
`get_user_group_members`, `check_messages_match_narrow`,
`get_scheduled_messages`, `get_drafts`, `get_read_receipts`,
`get_message_history`, `get_daily_summary` and `list_sessions` in extended mode.
Mixed-operation tools stay out because their names alone cannot establish that
a call is read-only.

`bot` keeps `BOT_TOOLS`: `wait_for_mentions`, `reply`, `server_info`,
`get_message`, `search_messages`, `get_streams`, `get_stream_topics`,
`resolve_user` and `get_users`. Every call uses the bot identity.

## Design intent

- Keep common workflows on a compact default registry.
- Move specialized operations to explicit extended mode.
- Keep the bot inbox and session binding in core mode so an agent can talk with
  its owner in Zulip without enabling the extended set.
