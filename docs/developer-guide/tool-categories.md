# Tool Categories

The registry lives in `src/zulipchat_mcp/tools/__init__.py`: `CORE_TOOLS` and
`register_core_tools` for the default surface, `register_extended_tools` for
the rest. Profiles in `src/zulipchat_mcp/core/tool_contract.py` narrow either
surface.

## Core mode (19 tools)

### Messaging and reactions (5)

- `send_message`
- `edit_message`
- `get_message`
- `add_reaction`
- `manage_message_flags`

### Agent bots (1, plus 1 in bridged agents)

- `teleport_chat`
- `ask_owner`, registered only when `ZULIPCHAT_AGENT_STATE` is set, that is,
  inside an agent launched by `zulipchat-mcp-agents`. It is not in `CORE_TOOLS`.

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

## Extended additions (34 tools, 53 total)

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
| `full` | 19 | 53 |
| `read-only` | 7 | 22 |

`read-only` keeps `READ_ONLY_TOOLS`: `server_info`, `get_message`,
`search_messages`, `get_streams`, `get_stream_topics`, `resolve_user` and
`get_users` in core, plus `get_stream_info`, `get_own_user`, `get_user`,
`get_user_status`, `get_user_presence`, `get_presence`, `get_user_groups`,
`get_user_group_members`, `check_messages_match_narrow`,
`get_scheduled_messages`, `get_drafts`, `get_read_receipts`,
`get_message_history`, `get_daily_summary` and `list_sessions` in extended mode.
Mixed-operation tools stay out because their names alone cannot establish that
a call is read-only.

## Design intent

- Keep common workflows on a compact default registry.
- Move specialized operations to explicit extended mode.
- Keep `teleport_chat` and session binding in core mode so an agent can reach
  its owner in Zulip without enabling the extended set.
