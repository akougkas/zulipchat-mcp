# Events API

Event tools are extended mode only.

## Tools

- `register_events(event_types, narrow=None, queue_lifespan_secs=300, ..., include_realm_state=False)`
- `get_events(queue_id, last_event_id, dont_block=False, timeout=10, ..., max_events=100)`
- `listen_events(event_types, duration=300, narrow=None, filters=None, poll_interval=1, ..., max_events=500)`
- `deregister_events(queue_id)`

## Examples

Register and poll:

```python
queue = await register_events(event_types=["message", "reaction"])
await get_events(queue_id=queue["queue_id"], last_event_id=queue["last_event_id"])
```

Short listener session:

```python
await listen_events(
    event_types=["message"],
    duration=120,
    poll_interval=2,
)
```

## Behavior notes

- `listen_events` handles registration and cleanup automatically.
- `listen_events` accepts `duration` up to 600 seconds and retries at most
  three consecutive failed polls. Unrecovered failures return `error`, or
  `partial` when events were collected; recovered failures appear in
  `polling_errors`.
- Queue lifespan is capped at 600 seconds.
- `get_events` returns at most `max_events` (1-100) events, oldest first, with
  `more_events=True` when it cut some off; poll again from the last returned
  event ID. `listen_events` stops at `max_events` (1-500) and reports
  `reached_max_events`.
- `register_events` returns only the queue by default. Pass
  `include_realm_state=True` for Zulip's initial state; oversized state is
  replaced by its keys and `realm_state_truncated=True`.
- These tools return events to the calling agent only; they do not wake an
  agent. To act on messages sent to a bot, run the
  [agent bridge](../integrations/agent-bots.md).
- Events are returned to the caller only. The server has no webhook and sends Zulip data to no other host.
