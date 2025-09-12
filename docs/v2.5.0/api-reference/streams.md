# Streams API Reference (Corrected)

The streams category provides comprehensive stream and topic management with basic analytics and settings management.

## Tool Overview

| Function | Purpose | Identity Support |
|----------|---------|------------------|
| [`manage_streams()`](#manage_streams) | Stream CRUD with bulk operations | User, Bot, Admin |
| [`manage_topics()`](#manage_topics) | Topic operations within streams | User, Admin |
| [`get_stream_info()`](#get_stream_info) | Stream details & metadata | User, Bot, Admin |
| [`stream_analytics()`](#stream_analytics) | Basic stream statistics (sampled) | User, Bot, Admin |
| [`manage_stream_settings()`](#manage_stream_settings) | Stream settings management | User |

## Functions

### `manage_streams()`

Manage streams with bulk operations support for creation, updates, subscriptions, and deletion.

#### Signature
```python
async def manage_streams(
    operation: Literal["list", "create", "update", "delete", "subscribe", "unsubscribe"],
    stream_ids: Optional[List[int]] = None,
    stream_names: Optional[List[str]] = None,
    properties: Optional[Dict[str, Any]] = None,
    principals: Optional[List[str]] = None,
    announce: bool = False,
    invite_only: bool = False,
    include_public: bool = True,
    include_subscribed: bool = True,
    include_all_active: bool = False,
    authorization_errors_fatal: bool = True,
    history_public_to_subscribers: Optional[bool] = None,
    stream_post_policy: Optional[int] = None,
    message_retention_days: Optional[int] = None
) -> Dict[str, Any]
```

#### Examples

**Create streams:**
```python
result = await manage_streams(
    operation="create",
    stream_names=["project-alpha", "project-beta"],
    properties={"description": "Project streams"},
    principals=["user@example.com"],
    announce=True
)
```

**Subscribe to streams:**
```python
result = await manage_streams(
    operation="subscribe",
    stream_names=["general", "random"],
    principals=["alice@example.com", "bob@example.com"]
)
```

#### Response Format

**Create operation:**
```python
{
    "status": "success",
    "operation": "create",
    "subscribed": {...},
    "already_subscribed": {...},
    "unauthorized": []
}
```

### `manage_topics()`

Perform operations on topics within streams.

#### Signature
```python
async def manage_topics(
    stream_id: int,
    operation: Literal["list", "move", "delete", "mark_read", "mute", "unmute"],
    source_topic: Optional[str] = None,
    target_topic: Optional[str] = None,
    target_stream_id: Optional[int] = None,
    propagate_mode: str = "change_all",
    include_muted: bool = True,
    max_results: int = 100,
    send_notification_to_old_thread: bool = True,
    send_notification_to_new_thread: bool = True
) -> Dict[str, Any]
```

#### Examples

**List topics:**
```python
result = await manage_topics(
    stream_id=123,
    operation="list"
)
```

**Move/rename topic:**
```python
result = await manage_topics(
    stream_id=123,
    operation="move",
    source_topic="old-discussion",
    target_topic="new-discussion",
    propagate_mode="change_all"
)
```

### `get_stream_info()`

Retrieve comprehensive stream information.

#### Signature
```python
async def get_stream_info(
    stream_id: Optional[int] = None,
    stream_name: Optional[str] = None,
    include_topics: bool = False,
    include_subscribers: bool = False,
    include_settings: bool = False,
    include_web_public: bool = False,
    include_default: bool = False
) -> Dict[str, Any]
```

#### Example
```python
result = await get_stream_info(
    stream_id=123,
    include_topics=True,
    include_subscribers=True
)
```

### `stream_analytics()`

Get basic stream statistics based on message samples (NOT comprehensive analytics).

#### Signature
```python
async def stream_analytics(
    stream_id: Optional[int] = None,
    stream_name: Optional[str] = None,
    time_period: Literal["day", "week", "month", "year"] = "week",
    include_message_stats: bool = True,
    include_user_activity: bool = True,
    include_topic_stats: bool = True
) -> Dict[str, Any]
```

**Note:** Analytics are approximated from recent message samples, not comprehensive data.

#### Example
```python
result = await stream_analytics(
    stream_id=123,
    time_period="week",
    include_message_stats=True,
    include_user_activity=True
)
```

#### Response Format
```python
{
    "status": "success",
    "stream_id": 123,
    "time_period": "week",
    "message_stats": {
        "recent_message_count": 250,
        "sample_size": 1000,
        "average_message_length": 125.5,
        "note": "Statistics based on recent message sample"
    },
    "user_activity": {
        "total_subscribers": 45,
        "subscriber_list": [...]
    },
    "topic_stats": {
        "total_topics": 12,
        "recent_topics": [...],
        "most_active_topics": [...]
    }
}
```

### `manage_stream_settings()`

Manage stream notification settings and permissions.

#### Signature
```python
async def manage_stream_settings(
    stream_id: int,
    operation: Literal["get", "update", "notifications", "permissions"],
    notification_settings: Optional[Dict[str, Any]] = None,
    permission_updates: Optional[Dict[str, Any]] = None,
    color: Optional[str] = None,
    pin_to_top: Optional[bool] = None
) -> Dict[str, Any]
```

#### Examples

**Get settings:**
```python
result = await manage_stream_settings(
    stream_id=123,
    operation="get"
)
```

**Update notifications:**
```python
result = await manage_stream_settings(
    stream_id=123,
    operation="notifications",
    notification_settings={
        "push_notifications": True,
        "email_notifications": False
    }
)
```

**Update appearance:**
```python
result = await manage_stream_settings(
    stream_id=123,
    operation="update",
    color="#ff6600",
    pin_to_top=True
)
```

## Important Notes

1. **No `validation_mode` parameter** - Validation is handled internally
2. **Bulk operations use plural parameters** - `stream_ids` not `stream_id` for bulk ops
3. **Use `principals` for user lists** - Email addresses, not user IDs
4. **Analytics are sampled** - Not comprehensive data analysis
5. **No AI features** - Basic statistics only

## Error Handling

Common error responses:

```python
{
    "status": "error",
    "error": "Stream 'nonexistent' not found",
    "operation": "update"
}
```

## Performance Considerations

- Stream operations are rate-limited
- Analytics are based on message samples (max 1000 messages)
- Use bulk operations when possible to reduce API calls
- Topic operations may be slow for large topics

---

**Related**: [Events API](events.md) | [Messaging API](messaging.md)