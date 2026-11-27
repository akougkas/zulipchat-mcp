# Tool Categories

The registry lives in `src/zulipchat_mcp/tools/__init__.py`: `CORE_TOOLS` and
`register_core_tools` for the default surface, `register_extended_tools` for
the rest. Profiles in `src/zulipchat_mcp/core/tool_contract.py` narrow either
surface.

## Core mode (13 tools)

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

### System (2)

- `server_info`
- `switch_identity`

## Extended additions (40 tools, 53 total)

### Users and presence (10)

- `get_own_user`, `get_user`, `get_user_status`, `update_status`
- `get_user_presence`, `get_presence`
- `get_user_groups`, `get_user_group_members`
- `manage_user_mute`, `set_typing`

### Channels and topics (3)

- `get_stream_info`, `resolve_topic`, `set_topic_visibility`

### Messages (7)

- `cross_post_message`, `get_read_receipts`, `get_message_history`
- `check_messages_match_narrow`, `update_message_flags_for_narrow`
- `mark_all_messages`, `get_daily_summary`

### Scheduled messages, reminders and drafts (11)

- `get_scheduled_messages`, `create_scheduled_message`,
  `update_scheduled_message`, `delete_scheduled_message`
- `get_reminders`, `create_reminder`, `delete_reminder`
- `get_drafts`, `create_draft`, `edit_draft`, `delete_draft`

### Events (4)

- `register_events`, `get_events`, `listen_events`, `deregister_events`

### Files (5)

- `upload_file`, `get_files`, `download_file`, `share_file`, `delete_file`

## Tool profiles

| Profile | Core | Extended |
| --- | --- | --- |
| `full` | 13 | 53 |
| `read-only` | 7 | 23 |
| `ask-owner` | `ask_owner` only | `ask_owner` only |

`read-only` keeps `READ_ONLY_TOOLS`: `server_info`, `get_message`,
`search_messages`, `get_streams`, `get_stream_topics`, `resolve_user` and
`get_users` in core, plus `get_stream_info`, `get_own_user`, `get_user`,
`get_user_status`, `get_user_presence`, `get_presence`, `get_user_groups`,
`get_user_group_members`, `check_messages_match_narrow`,
`get_scheduled_messages`, `get_reminders`, `get_drafts`, `get_files`,
`get_read_receipts`,
`get_message_history` and `get_daily_summary` in extended mode.
Each tool does one kind of operation, so its annotations say whether it reads,
writes or destroys; the remaining tools that write stay out. `ask-owner` is the profile the agent bridge gives the
agents it launches when their agent file keeps the default `zulip_tools = "ask"`.

## Design intent

- Keep common workflows on a compact default registry.
- Move specialized operations to explicit extended mode.
- Keep `teleport_chat` in core mode so an agent can hand its conversation to
  the owner's agent bot without enabling the extended set.
