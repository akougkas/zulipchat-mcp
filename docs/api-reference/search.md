# Search API

## Core tool

- `search_messages(query=None, stream=None, topic=None, sender=None, ..., limit=50, sort_by="relevance")`

## Extended tools

- `advanced_search(query, search_type=None, stream=None, topic=None, sender=None, ..., aggregations=None)`
- `construct_narrow(...)`
- `check_messages_match_narrow(msg_ids, narrow)`

## Examples

Search recent messages from a stream:

```python
await search_messages(
    query="deploy",
    stream="engineering",
    last_hours=24,
    limit=30,
    sort_by="newest",
)
```

Build a narrow filter:

```python
await construct_narrow(
    stream="engineering",
    topic="deploy",
    is_unread=True,
    has_link=True,
)
```

Run multi-scope search:

```python
await advanced_search(
    query="incident",
    search_type=["messages", "users", "streams"],
    aggregations=["count_by_user", "count_by_stream"],
)
```

## Behavior notes

- `search_messages` resolves non-email sender values with fuzzy user lookup.
- Time filters use UTC; ISO timestamps with offsets are converted to UTC and
  timestamps without a timezone are interpreted as UTC. Results are bounded
  samples of 1–1000 messages, sorted at the requested end of the interval.
  `sort_by="relevance"` currently uses newest-first ordering, not a relevance score.
- Newest-first searches with a lower time bound work on older Zulip versions.
  An upper bound, or oldest-first search with a lower bound, uses date anchors
  and requires Zulip 12 / feature level 445 or later.
- Zulip narrow filters cannot encode timestamps. `construct_narrow` rejects
  `after_time`/`before_time` and directs callers to `search_messages`. The Python
  narrow-helper time methods also raise an error instead of generating text
  searches for strings such as `after:2026-09-01`.
- `advanced_search` also supports topic-name search when `stream` is supplied.
  Failed scopes are included in the results and produce `status="partial"` or
  `status="error"`. Counts and aggregations describe the returned sample.
