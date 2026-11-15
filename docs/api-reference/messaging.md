# Messaging API

## Core tools

- `send_message(type, to, content, topic=None, allow_duplicate=False, as_bot=False)`
- `edit_message(message_id, content=None, topic=None, stream_id=None, propagate_mode="change_one", send_notification_to_old_thread=False, send_notification_to_new_thread=True)`
- `get_message(message_id, fresh=False, content_format="rendered_html")`: `content_format="markdown"` returns the source text
- `add_reaction(message_id, emoji_name, emoji_code=None, reaction_type="unicode_emoji", remove=False)`
- `manage_message_flags(flag, action, scope="narrow", stream_id=None, topic_name=None, sender_email=None, narrow=None)`

To post one message as the bot, pass `as_bot=True`. Handing a conversation to
an agent bot uses `teleport_chat`; see the [Agents API](agents.md).

## Extended tools

- `cross_post_message(source_message_id, target_streams, target_topic=None, add_reference=True, custom_prefix=None)`
- `update_message_flags_for_narrow(narrow, op, flag, anchor="newest", include_anchor=True, num_before=50, num_after=50)`
- `get_read_receipts(message_id)`
- `get_message_history(message_id)`
- `get_scheduled_messages()`
- `manage_scheduled_message(action, type=None, to=None, content=None, topic=None, scheduled_delivery_timestamp=None, read_by_sender=True, scheduled_message_id=None)`
- `manage_reminders(action, message_id=None, deliver_at=None, note=None, reminder_id=None)`
- `get_drafts()`
- `create_draft(type, to, content, topic="", timestamp=None)`
- `edit_draft(draft_id, type, to, content, topic="", timestamp=None)`
- `delete_draft(draft_id)`

## Examples

Send a channel message:

```python
await send_message(
    type="channel",
    to="engineering",
    topic="deploy",
    content="Deploy starts at 15:00 UTC",
)
```

Send a direct message by name:

```python
await send_message(type="direct", to=["Jaime"], content="Build is green.")
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

Remind yourself about a message tomorrow morning:

```python
await manage_reminders(
    action="create",
    message_id=12345,
    deliver_at="2026-11-16T09:00:00",
    note="Follow up on the deploy",
)
```

## Behavior notes

- `type` accepts `channel` or `stream` for channel messages and `direct` or
  `private` for direct messages. Channel messages require a topic; `to` takes a
  channel name (a leading `#` is ignored) or ID.
- Direct-message recipients may be names, emails or user IDs. A name must match
  exactly one active user by full name, first name or a unique full-name prefix.
  Otherwise nothing is sent and the result carries `AMBIGUOUS_RECIPIENT` or
  `UNKNOWN_RECIPIENT` with up to five `candidates`.
- A successful send returns `message_id`, `sent_as` and `message_link`.
- An identical send (same sender, recipients, topic and content) within two
  minutes of a successful one is not posted again. The result repeats the
  original `message_id` with `duplicate_suppressed=True`. Pass
  `allow_duplicate=True` only for a deliberate repeat.
- `as_bot=True` sends one message with the bot credentials. It is available over
  stdio only and fails when no bot is configured.
- `add_reaction` validates against the approved agent emoji list;
  `remove=True` takes the reaction back.
- `send_message` and `edit_message` truncate content above 50,000 characters.
- `get_read_receipts` returns `readers` as `{user_id, name}` and a `count`.
  Organizations can disable read receipts.
- `get_message_history` lists edits oldest first. The first entry holds the
  original content and topic; later entries carry a content `diff` and
  `[old, new]` pairs for `topic` and `stream`. `edit_count` excludes the original.
- `manage_reminders` uses Zulip's reminder endpoints (feature levels 381, 399
  and 415); older servers return an error. A naive `deliver_at` is read as UTC.
  `list` returns `reminder_id`, `message_id`, `deliver_at` and `failed`.
- `manage_scheduled_message` accepts the same `type` aliases as `send_message`;
  `to` is a channel ID or a list of user IDs.
- Draft tools take `type="stream"` or `type="private"` only.
- Individual reads reuse identity-scoped snapshots for up to 15 seconds;
  inspect `cache`, or set `fresh=True` when a new observation is needed.
- Cross-posting retrieves raw Markdown. Backend errors retain available codes
  and retry delays; resolve uncertain send outcomes before retrying a write.
