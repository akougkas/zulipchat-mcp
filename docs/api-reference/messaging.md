# Messaging API

## Core tools

- `send_message(type, to, content, topic=None)`
- `edit_message(message_id, content=None, topic=None, stream_id=None, propagate_mode="change_one", ...)`
- `get_message(message_id)`
- `add_reaction(message_id, emoji_name, emoji_code=None, reaction_type="unicode_emoji")`
- `manage_message_flags(flag, action, scope="narrow", stream_id=None, topic_name=None, sender_email=None, narrow=None)`

## Extended tools

- `cross_post_message(source_message_id, target_streams, target_topic=None, add_reference=True, custom_prefix=None)`
- `toggle_reaction(message_id, emoji_name, action="add", emoji_code=None, reaction_type="unicode_emoji")`
- `update_message_flags_for_narrow(narrow, op, flag, anchor="newest", include_anchor=True, num_before=50, num_after=50)`
- `get_scheduled_messages()`
- `manage_scheduled_message(action, type=None, to=None, content=None, topic=None, scheduled_delivery_timestamp=None, read_by_sender=True, scheduled_message_id=None)`

## Examples

Send a stream message:

```python
await send_message(
    type="stream",
    to="engineering",
    topic="deploy",
    content="Deploy starts at 15:00 UTC",
)
```

Edit message content and topic:

```python
await edit_message(
    message_id=12345,
    content="Deploy starts at 15:30 UTC",
    topic="deploy-update",
    propagate_mode="change_all",
)
```

Mark a topic as read:

```python
await manage_message_flags(
    flag="read",
    action="add",
    scope="topic",
    stream_id=10,
    topic_name="deploy",
)
```

## Behavior notes

- Stream messages require a topic.
- `add_reaction` validates against the approved agent emoji list.
- `send_message` and `edit_message` truncate very large content payloads.
- Scheduled message tools are in extended mode.
