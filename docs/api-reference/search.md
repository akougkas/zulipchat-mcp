# Search API

## Core tool

- `search_messages(query=None, stream=None, topic=None, sender=None, has_attachment=None, has_link=None, has_image=None, is_private=None, is_starred=None, is_mentioned=None, last_hours=None, last_days=None, after_time=None, before_time=None, limit=20, sort_by="relevance", fresh=False, content_format="markdown", cursor=None, is_unread=None)`

## Extended tools

- `check_messages_match_narrow(msg_ids, narrow)`
- `get_daily_summary(streams=None, hours_back=24)`: at most 50 channels

## Examples

Read the latest messages in a channel topic:

```python
await search_messages(stream="engineering", topic="deploy")
```

Search the last day of a channel, newest first:

```python
await search_messages(
    query="deploy",
    stream="engineering",
    last_hours=24,
    limit=30,
    sort_by="newest",
)
```

Unread messages that mention you:

```python
await search_messages(is_unread=True, is_mentioned=True)
```

## Result shape

```json
{
  "status": "success",
  "count": 2,
  "sample": {"completeness": "partial", "ordering": "newest_first",
             "next_cursor": "48213:9f2c...", "channel": "engineering"},
  "messages": [
    {"id": 48220, "from": "Jaime Ruiz", "time": "2026-11-14T16:02+00:00",
     "topic": "deploy", "text": "Rolled back.", "reactions": {"thumbs_up": 2},
     "unread": true}
  ]
}
```

Each row has `id`, `from`, `time` (UTC, minute precision) and `text`. The other
keys appear only when they carry information: `channel` and `topic` when the
filter does not already fix them, `dm` for direct messages, `reactions` as
emoji name to count, `unread`, `starred`, and `truncated` when the text exceeds
1,000 characters.

## Behavior notes

- `stream` plus `topic` with no `query` reads that thread.
- `sender` accepts a name or an email. Names resolve with fuzzy user lookup;
  an ambiguous or unknown name returns an error with suggestions.
- Rows default to Markdown source. `content_format="rendered_html"` returns
  rendered excerpts instead, which are several times larger.
- `limit` is 1–1000. `sort_by="relevance"` uses newest-first ordering; it is
  not a relevance score.
- Time filters use UTC; ISO timestamps with offsets are converted to UTC and
  timestamps without a timezone are interpreted as UTC. Results are sorted at
  the requested end of the interval.
- Newest-first searches with a lower time bound work on older Zulip versions.
  An upper bound, or oldest-first search with a lower bound, uses date anchors
  and requires Zulip 12 / feature level 445 or later.
- `sample` holds `completeness`, `ordering`, `next_cursor` while more matches
  remain, `truncated_excerpts`, the applied `after_time_utc`/`before_time_utc`,
  and the fixed `channel`/`topic`.
- Paging: while `sample.next_cursor` is set, `completeness` is `partial`. Repeat
  the same call with `cursor=<next_cursor>` to fetch the next page, which starts
  after that message. The cursor is bound to the account, filters, time window
  and order, and is rejected for any other search. When `next_cursor` is absent,
  `completeness` is `exhausted_visible_query`: every message visible to this
  identity in the window has been returned. Response metadata precedes
  `messages`, so a host that truncates a long result still shows it.
- Use selected message IDs with `get_message` for full content.
- Successful windows are cached for 15 seconds by identity and exact upstream
  request. `fresh=True` bypasses reuse. Honor returned `RATE_LIMIT_HIT` retry
  delays rather than repeating a throttled query. See [API efficiency](../developer-guide/zulip-api-proxy.md).
- `get_daily_summary` returns counts only, with no model call. Its `summary`
  holds `total_messages`, `streams` with each channel's `message_count` and
  per-topic counts, and `top_senders` for the last `hours_back` hours. Without
  `streams` on feature level 445 or later, one request covers every public
  channel up to 1,000 messages and `truncated` reports more. Channels that fail
  are listed in `unavailable_streams`.
- `check_messages_match_narrow` reports which of the given IDs match a Zulip
  narrow. Narrows cannot encode timestamps; use `search_messages` time filters.
