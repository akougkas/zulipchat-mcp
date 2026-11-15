# Channels and Topics API

Zulip now calls streams "channels". Tool and parameter names keep the older
`stream` spelling.

## Core tools

- `get_streams(include_subscribed=True, include_public=True, verbose=False)`: returns `stream_id`, `name`, `description`, `invite_only`, `is_web_public` and `is_archived` per channel; `verbose=True` returns raw Zulip stream objects
- `get_stream_topics(stream_id=None, max_results=100, stream_name=None)`: pass either the ID or the name

## Extended tools

- `get_stream_info(stream_name=None, stream_id=None, include_subscribers=False, include_topics=False)`
- `resolve_topic(stream, topic, resolved=True)`
- `set_topic_visibility(stream, topic, policy)`

## Examples

List channels:

```python
await get_streams(include_subscribed=True)
```

Read channel details by name:

```python
await get_stream_info(stream_name="engineering", include_topics=True)
```

Mark a topic resolved:

```python
await resolve_topic(stream="engineering", topic="deploy")
```

Follow a topic:

```python
await set_topic_visibility(stream="engineering", topic="deploy", policy="followed")
```

## Behavior notes

- `get_stream_info` returns `partial` with a component error when requested
  subscribers or topics fail; basic channel information stays usable.
- `resolve_topic` renames the whole topic to or from the `✔ ` prefix through
  its latest message. It is idempotent: a topic already in the requested state
  returns `changed=False`. `stream` is a channel name or ID.
- `set_topic_visibility` changes only your own view of the topic. `policy` is
  `inherit`, `muted`, `unmuted` or `followed`. Servers before feature level 170
  support only `muted` and `inherit`; `followed` needs feature level 219.
- Editing a topic name or moving messages uses `edit_message`.
