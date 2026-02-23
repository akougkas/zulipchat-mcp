# Events API

Event tools are extended mode only.

## Tools

- `register_events(event_types, narrow=None, queue_lifespan_secs=300, ...)`
- `get_events(queue_id, last_event_id, dont_block=False, timeout=10, ...)`
- `listen_events(event_types, duration=300, narrow=None, filters=None, poll_interval=1, ...)`
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
- Queue lifespan and timeout values are capped by tool logic.
- Optional webhook callback is best-effort.
