# Users API

## Core tools

- `resolve_user(name)`
- `get_users(client_gravatar=True, include_custom_profile_fields=False, user_ids=None)`
- `get_own_user()`

## Extended tools

- `get_user(user_id=None, email=None, include_custom_profile_fields=False)`
- `get_user_status(user_id)`
- `update_status(status_text=None, emoji_name=None, emoji_code=None, reaction_type="unicode_emoji")`
- `get_user_presence(user_id_or_email)`
- `get_presence()`
- `get_user_groups(include_deactivated_groups=False)`
- `get_user_group_members(user_group_id, direct_member_only=False)`
- `is_user_group_member(user_group_id, user_id, direct_member_only=False)`
- `manage_user_mute(action, muted_user_id)`

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
await manage_user_mute(action="mute", muted_user_id=42)
```

## Behavior notes

- `resolve_user` is fuzzy and cache-backed.
- `manage_user_mute` only affects the authenticated user's mute list.
- User-management tools are identity-aware through `switch_identity`.
