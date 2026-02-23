# Streams and Topics API

## Core tools

- `get_streams(include_subscribed=True, include_public=True)`
- `get_stream_info(stream_name=None, stream_id=None, include_subscribers=False, include_topics=False)`
- `get_stream_topics(stream_id, max_results=100)`

## Extended tools

- `agents_channel_topic_ops(operation, source_topic, target_topic=None, propagate_mode="change_all")`

## Examples

List streams:

```python
await get_streams(include_subscribed=True)
```

Read stream details by name:

```python
await get_stream_info(stream_name="engineering", include_topics=True)
```

Move topic in `Agents-Channel`:

```python
await agents_channel_topic_ops(
    operation="move",
    source_topic="Agents/Chat/abc123",
    target_topic="Agents/Chat/def456",
)
```

## Behavior notes

- Stream tools are read-focused.
- `agents_channel_topic_ops` always uses bot identity and is limited to `Agents-Channel`.
- Deleting a topic through `agents_channel_topic_ops` requires `--unsafe`.
