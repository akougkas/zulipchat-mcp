# System API

## Tools

- `switch_identity(identity)`
- `server_info()`

Both are core tools.

## Examples

Switch to bot identity:

```python
await switch_identity("bot")
```

Get runtime capabilities:

```python
await server_info()
```

## Tool profiles

`--tool-profile` limits which tools are listed and callable. A denied call
returns `POLICY_DENIED`.

| Profile | Tools |
| --- | --- |
| `full` (default) | 21 core tools, or 55 with `--extended-tools` |
| `read-only` | 7 core reads, or 22 with `--extended-tools` |
| `bot` | `wait_for_mentions`, `reply`, `server_info`, `get_message`, `search_messages`, `get_streams`, `get_stream_topics`, `resolve_user`, `get_users` |

The `bot` profile serves a session the owner starts from Zulip. It requires bot
credentials, cannot run with `--unsafe`, and makes every call with the bot
identity, so an answer posted in a channel can only contain what the bot could
already see.

## Behavior notes

- `switch_identity("bot")` fails if bot credentials are not configured.
  Identity switching is available over stdio only.
- `server_info` reports version, available identities, the Zulip site, the
  mention allow policy, and `capabilities` with the active `tool_profile`,
  transport and `enabled_tools`.
