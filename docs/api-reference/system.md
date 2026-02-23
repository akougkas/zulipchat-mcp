# System API

## Tools

- `switch_identity(identity)`
- `server_info()`

## Examples

Switch to bot identity:

```python
await switch_identity("bot")
```

Get runtime capabilities:

```python
await server_info()
```

## Behavior notes

- `switch_identity("bot")` fails if bot credentials are not configured.
- `server_info` reports version, available identities, and current Zulip site metadata.
