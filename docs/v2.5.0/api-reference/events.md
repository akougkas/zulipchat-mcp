# Events API Reference (Corrected)

The events category provides real-time event streaming capabilities with stateless queue management and basic webhook integration.

## Tool Overview

| Function | Purpose | Identity Support |
|----------|---------|------------------|
| [`register_events()`](#register_events) | Create event queue | User, Bot |
| [`get_events()`](#get_events) | Poll events from queue | User, Bot |
| [`listen_events()`](#listen_events) | Poll events with optional webhooks | User, Bot |

## Event System Architecture

### Key Facts
- **Queue lifetime**: Maximum 300 seconds (5 minutes) - NOT 10 minutes
- **Stateless design**: No persistent server state
- **Polling-based**: Not true continuous streaming
- **Auto-cleanup**: Queues expire automatically via asyncio tasks

## Functions

### `register_events()`

Register for real-time events by creating an event queue.

#### Signature
```python
async def register_events(
    event_types: List[str],
    narrow: Optional[List[Dict[str, Any]]] = None,
    all_public_streams: bool = False,
    queue_lifespan_secs: int = 300,
    fetch_event_types: Optional[List[str]] = None,
    client_capabilities: Optional[Dict[str, Any]] = None,
    slim_presence: bool = False,
    include_subscribers: bool = False,
    client_gravatar: bool = False
) -> Dict[str, Any]
```

#### Parameters
- **`event_types`** (List[str]): Event types to subscribe to
- **`narrow`** (List[Dict]): Filter for message events only
- **`all_public_streams`** (bool): Subscribe to all public streams
- **`queue_lifespan_secs`** (int): Queue auto-cleanup time (max 300 seconds)
- **`fetch_event_types`** (List[str]): Event types for initial state fetch
- **`client_capabilities`** (Dict): Client capability declarations
- **`slim_presence`** (bool): Use slim presence format
- **`include_subscribers`** (bool): Include subscriber lists in stream events
- **`client_gravatar`** (bool): Include gravatar URLs

#### Example
```python
queue = await register_events(
    event_types=["message", "reaction"],
    narrow=[{"operator": "stream", "operand": "general"}],
    queue_lifespan_secs=300,
    slim_presence=True
)
```

#### Response Format
```python
{
    "status": "success",
    "queue_id": "abc123def456",
    "last_event_id": -1,
    "event_types": ["message", "reaction"],
    "lifespan_seconds": 300,
    "max_message_id": 12345,
    "initial_state": {...}
}
```

### `get_events()`

Poll events from a registered queue.

#### Signature
```python
async def get_events(
    queue_id: str,
    last_event_id: int,
    dont_block: bool = False,
    timeout: int = 10,
    user_client: Optional[str] = None,
    apply_markdown: bool = True,
    client_gravatar: bool = False
) -> Dict[str, Any]
```

#### Parameters
- **`queue_id`** (str): Queue ID from register_events
- **`last_event_id`** (int): Last processed event ID
- **`dont_block`** (bool): Return immediately even if no events
- **`timeout`** (int): Long-polling timeout (default: 10 seconds)
- **`user_client`** (str): User client identifier
- **`apply_markdown`** (bool): Apply markdown formatting
- **`client_gravatar`** (bool): Include gravatar URLs

#### Example
```python
events = await get_events(
    queue_id="abc123def456",
    last_event_id=42,
    timeout=10
)
```

#### Response Format
```python
{
    "status": "success",
    "queue_id": "abc123def456",
    "events": [...],
    "event_count": 5,
    "last_event_id": 47,
    "queue_still_valid": true
}
```

### `listen_events()`

Simple event listener with polling and optional webhook support.

#### Signature
```python
async def listen_events(
    event_types: List[str],
    callback_url: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    duration: int = 300,
    narrow: Optional[List[Dict[str, Any]]] = None,
    all_public_streams: bool = False,
    poll_interval: int = 1,
    max_events_per_poll: int = 100
) -> Dict[str, Any]
```

#### Parameters
- **`event_types`** (List[str]): Event types to listen for
- **`callback_url`** (str): Optional webhook URL for event delivery
- **`filters`** (Dict): Event filtering criteria
- **`duration`** (int): Maximum listening duration in seconds
- **`narrow`** (List[Dict]): Message filters
- **`all_public_streams`** (bool): Subscribe to all public streams
- **`poll_interval`** (int): Seconds between polls
- **`max_events_per_poll`** (int): Maximum events to process per poll

**Note:** This is NOT continuous streaming - it polls in a loop.

#### Example
```python
result = await listen_events(
    event_types=["message"],
    duration=300,
    callback_url="https://example.com/webhook",
    poll_interval=2,
    max_events_per_poll=50
)
```

#### Response Format
```python
{
    "status": "success",
    "events": [...],  # Full event list
    "total_events": 42,
    "webhook_notifications_sent": 5,
    "duration_seconds": 300,
    "queue_id": "abc123def456"
}
```

## Event Types

Common event types include:
- `message` - New messages
- `reaction` - Emoji reactions
- `subscription` - Stream subscriptions
- `realm_user` - User changes
- `presence` - User presence
- `typing` - Typing indicators
- `update_message` - Message edits

## Important Notes

1. **No `validation_mode` parameter** - Not exposed to API users
2. **Queue lifetime is 5 minutes max** - Not 10 minutes as some docs claim
3. **Polling-based system** - Not true real-time streaming
4. **Basic webhook support** - Simpler than documented
5. **No batch_size or max_queue_size** - Use max_events_per_poll instead

## Error Handling

Common errors:
```python
{
    "status": "error",
    "error": "Invalid event queue ID",
    "queue_still_valid": false
}
```

## Best Practices

1. **Keep queues alive**: Poll at least every 60 seconds
2. **Handle queue expiration**: Re-register when queues expire
3. **Use appropriate timeouts**: Balance responsiveness vs resource usage
4. **Filter events**: Subscribe only to needed event types

---

**Related**: [Streams API](streams.md) | [Messaging API](messaging.md)