# Users API

## Core tools

- `resolve_user(name)`
- `get_users(client_gravatar=True, include_custom_profile_fields=False, user_ids=None, verbose=False, role=None, limit=200, cursor=None)`: returns at most `limit` users (1-1000) ordered by user ID, with `total` and `next_cursor` when more remain, and `user_id`, `full_name`, `email`, `role`, `is_bot`, `is_active`, `timezone` (and `profile_data` when requested) per user; `verbose=True` returns raw Zulip user objects

## Extended tools

- `get_own_user()`
- `get_user(user_id=None, email=None, include_custom_profile_fields=False)`
- `get_user_status(user_id)`
- `update_status(status_text=None, emoji_name=None, emoji_code=None, reaction_type="unicode_emoji")`
- `get_user_presence(user_id_or_email)`
- `get_presence(limit=200, cursor=None)`: one page of presence entries (1-1000), with `next_cursor` when more remain
- `get_user_groups(include_deactivated_groups=False)`
- `get_user_group_members(user_group_id, direct_member_only=False)`
- `manage_user_mute(muted_user_id, action="mute")`
- `set_typing(op, to=None, stream_id=None, topic=None)`

## Examples

Resolve a display name to email:

```python
await resolve_user("Jaime")
```

Fetch a specific user:

```python
await get_user(email="jaime@example.com")
```

Mute a user:

```python
await manage_user_mute(muted_user_id=42, action="mute")
```

Show a typing indicator in a channel topic:

```python
await set_typing(op="start", stream_id=10, topic="deploy")
```

## Behavior notes

- `resolve_user` is fuzzy and cache-backed. No match is a `USER_NOT_FOUND`
  error; several close matches are `AMBIGUOUS_USER` with candidates. `send_message` resolves direct
  recipients by name itself, so a separate lookup is rarely needed.
- `manage_user_mute` only affects the authenticated user's mute list.
- `set_typing` takes exactly one of `to` (user IDs) or `stream_id` plus `topic`.
- To check group membership, read `get_user_group_members`.
- User tools act with the current identity, which `switch_identity` selects.
