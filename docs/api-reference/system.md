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
| `full` (default) | 13 core tools, or 45 with `--extended-tools` |
| `read-only` | 7 core reads, or 21 with `--extended-tools` |
| `ask-owner` | `ask_owner` only, for agents the bridge launches |

Inside an agent launched by the [agent bridge](../integrations/agent-bots.md),
the full profile adds `ask_owner`, so `server_info` lists 14 core tools there.

## Behavior notes

- `switch_identity("bot")` fails if bot credentials are not configured.
  Identity switching is available over stdio only.
- `server_info` reports version, available identities, the Zulip site, and
  `capabilities` with the active `tool_profile`, transport and
  `enabled_tools`.
