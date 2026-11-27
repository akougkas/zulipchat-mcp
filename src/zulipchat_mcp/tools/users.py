"""User management tools for ZulipChat MCP v0.4.0.

Clean READ-ONLY user operations based on Zulip API endpoints.
No user creation/editing - just reading, searching, and matching users.
"""

import asyncio
import re
from typing import Annotated, Any, Literal
from urllib.parse import quote

from pydantic import Field

from ..config import get_client
from ..core.errors import api_error, internal_error, tool_error
from .params import Cursor, Name, UserId, page_size


def validate_email(email: str) -> bool:
    """Basic email validation."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


# Zulip's numeric roles, by the name an agent would ask for.
ROLES: dict[Any, str] = {
    100: "owner",
    200: "admin",
    300: "moderator",
    400: "member",
    600: "guest",
}


def _user_row(user: dict[str, Any]) -> dict[str, Any]:
    """One member in few tokens: flags only when set, role by name."""
    row: dict[str, Any] = {
        "user_id": user.get("user_id"),
        "name": user.get("full_name"),
        "email": user.get("email"),
        "role": ROLES.get(user.get("role"), user.get("role")),
    }
    if user.get("is_bot"):
        row["bot"] = True
    if user.get("is_active") is False:
        row["inactive"] = True
    if user.get("profile_data"):
        row["profile_data"] = user["profile_data"]
    return row


def _page(
    rows: list[Any], key: Any, limit: int, cursor: str | None
) -> tuple[list[Any], dict[str, Any]]:
    """Rows sorted by key, the page after cursor, and the paging state.

    The cursor is the key of the last row returned, so a page boundary stays
    put when members join or leave between calls.
    """
    rows = sorted(rows, key=lambda row: str(key(row)).zfill(20))
    start = 0
    if cursor is not None:
        keys = [str(key(row)) for row in rows]
        mark = cursor.zfill(20)
        start = next((i for i, k in enumerate(keys) if k.zfill(20) > mark), len(rows))
    page = rows[start : start + limit]
    state: dict[str, Any] = {"total": len(rows), "returned": len(page)}
    if start + limit < len(rows) and page:
        state["next_cursor"] = str(key(page[-1]))
    return page, state


async def get_users(
    client_gravatar: Annotated[
        bool, Field(description="Omit Gravatar avatar URLs (verbose only).")
    ] = True,
    include_custom_profile_fields: Annotated[
        bool, Field(description="Add each member's custom profile fields.")
    ] = False,
    user_ids: Annotated[
        list[int] | None,
        Field(max_length=1000, description="Only these user IDs."),
    ] = None,
    verbose: Annotated[
        bool,
        Field(
            description="Return Zulip's full user objects instead of ID, name, "
            "email and role."
        ),
    ] = False,
    role: Annotated[
        Literal["owner", "admin", "moderator", "member", "guest"] | None,
        Field(description="Only members with this role."),
    ] = None,
    limit: Annotated[int, page_size(1000, "members, ordered by user ID")] = 200,
    cursor: Cursor = None,
) -> dict[str, Any]:
    """Organization members; role narrows to one role. Set verbose for raw objects."""
    if not 1 <= limit <= 1000:
        return tool_error("limit must be between 1 and 1000")
    client = get_client()

    try:
        result = await asyncio.to_thread(
            client.get_users,
            client_gravatar=client_gravatar,
            include_custom_profile_fields=include_custom_profile_fields,
            user_ids=user_ids,
        )

        if result.get("result") == "success":
            users = result.get("members", [])
            if role is not None:
                users = [u for u in users if ROLES.get(u.get("role")) == role]
            users, state = _page(users, lambda u: u.get("user_id", 0), limit, cursor)
            if not verbose:
                users = [_user_row(user) for user in users]
            return {"status": "success", "count": len(users), **state, "users": users}
        else:
            return api_error(result, "Failed to get users")

    except Exception as e:
        return internal_error(e)


async def get_user_by_id(
    user_id: int,
    client_gravatar: bool = True,
    include_custom_profile_fields: bool = False,
) -> dict[str, Any]:
    """Get specific user by ID (READ-ONLY)."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            client.get_user_by_id, user_id, include_custom_profile_fields
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "user": result.get("user", {}),
            }
        else:
            return api_error(result, "User not found")

    except Exception as e:
        return internal_error(e)


async def get_user_by_email(
    email: str,
    client_gravatar: bool = True,
    include_custom_profile_fields: bool = False,
) -> dict[str, Any]:
    """Get specific user by email (READ-ONLY)."""
    if not validate_email(email):
        return tool_error(f"Invalid email format: {email}")

    client = get_client()

    try:
        result = await asyncio.to_thread(
            client.get_user_by_email, email, include_custom_profile_fields
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "user": result.get("user", {}),
            }
        else:
            return api_error(result, "User not found")

    except Exception as e:
        return internal_error(e)


async def get_own_user() -> dict[str, Any]:
    """Get information about the current user (READ-ONLY)."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint("users/me", method="GET", request={})
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "user": {
                    "user_id": result.get("user_id"),
                    "email": result.get("email"),
                    "full_name": result.get("full_name"),
                    "avatar_url": result.get("avatar_url"),
                    "is_admin": result.get("is_admin"),
                    "is_owner": result.get("is_owner"),
                    "is_bot": result.get("is_bot"),
                    "role": result.get("role"),
                    "delivery_email": result.get("delivery_email"),
                    "profile_data": result.get("profile_data", {}),
                },
            }
        else:
            return api_error(result, "Failed to get own user")

    except Exception as e:
        return internal_error(e)


async def get_user_status(user_id: UserId) -> dict[str, Any]:
    """Get user's status (away, status text, emoji) (READ-ONLY)."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"users/{user_id}/status", method="GET", request={}
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "user_id": user_id,
                "user_status": result.get("status", {}),
            }
        else:
            return api_error(result, "Failed to get user status")

    except Exception as e:
        return internal_error(e)


async def update_status(
    status_text: Annotated[
        str | None,
        Field(max_length=60, description='Status text; "" clears it.'),
    ] = None,
    emoji_name: Annotated[
        str | None,
        Field(
            max_length=50, description='Status emoji name, e.g. "coffee"; "" clears it.'
        ),
    ] = None,
    emoji_code: Annotated[
        str | None,
        Field(max_length=50, description="Emoji code; needed for realm emoji."),
    ] = None,
    reaction_type: Annotated[
        Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"],
        Field(description="Kind of emoji named by emoji_name."),
    ] = "unicode_emoji",
) -> dict[str, Any]:
    """Update your own status text and emoji."""
    client = get_client()

    try:
        request_data = {}
        if status_text is not None:
            if len(status_text) > 60:
                return tool_error("Status text must be 60 characters or less")
            request_data["status_text"] = status_text

        if emoji_name is not None:
            request_data["emoji_name"] = emoji_name
        if emoji_code is not None:
            request_data["emoji_code"] = emoji_code
        if emoji_name or emoji_code:
            request_data["reaction_type"] = reaction_type

        if not request_data:
            return tool_error("Must provide status_text, emoji_name, or emoji_code")

        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "users/me/status", method="POST", request=request_data
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "updated_status": request_data,
            }
        else:
            return api_error(result, "Failed to update status")

    except Exception as e:
        return internal_error(e)


async def get_user_presence(
    user_id_or_email: Annotated[
        Name | int, Field(description="The user's ID or email.")
    ],
) -> dict[str, Any]:
    """Get presence information for a specific user (READ-ONLY)."""
    if isinstance(user_id_or_email, bool):
        return tool_error("user_id_or_email must be a positive user ID or email")
    if isinstance(user_id_or_email, int):
        if user_id_or_email <= 0:
            return tool_error("user_id_or_email must be a positive user ID or email")
        segment = str(user_id_or_email)
    elif user_id_or_email.isdigit() and int(user_id_or_email) > 0:
        segment = user_id_or_email
    elif validate_email(user_id_or_email):
        segment = quote(user_id_or_email, safe="@")
    else:
        return tool_error("user_id_or_email must be a positive user ID or email")

    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"users/{segment}/presence", method="GET", request={}
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "user_id_or_email": user_id_or_email,
                "presence": result.get("presence", {}),
            }
        else:
            return api_error(result, "Failed to get user presence")

    except Exception as e:
        return internal_error(e)


async def get_presence(
    limit: Annotated[int, page_size(1000, "users' presence, ordered by key")] = 200,
    cursor: Cursor = None,
) -> dict[str, Any]:
    """Get presence information for all users in organization (READ-ONLY)."""
    if not 1 <= limit <= 1000:
        return tool_error("limit must be between 1 and 1000")
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "realm/presence", method="GET", request={}
            )
        )

        if result.get("result") == "success":
            presences = result.get("presences") or {}
            keys, state = _page(list(presences), str, limit, cursor)
            return {
                "status": "success",
                "server_timestamp": result.get("server_timestamp"),
                "users_count": len(keys),
                **state,
                "presences": {key: presences[key] for key in keys},
            }
        else:
            return api_error(result, "Failed to get presence")

    except Exception as e:
        return internal_error(e)


async def get_user_groups(
    include_deactivated_groups: Annotated[
        bool, Field(description="Include deactivated groups.")
    ] = False,
    verbose: Annotated[
        bool,
        Field(
            description="Return Zulip's full group records, member lists and "
            "permission settings included."
        ),
    ] = False,
) -> dict[str, Any]:
    """User groups with member counts; verbose returns Zulip's full records."""
    client = get_client()

    try:
        request_data = {"include_deactivated_groups": include_deactivated_groups}
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "user_groups", method="GET", request=request_data
            )
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to get user groups")
        groups = result.get("user_groups", [])
        if not verbose:
            # Permission-group settings and member lists dwarf what an agent
            # needs to pick a group; get_user_group_members lists members.
            groups = [
                {
                    "id": group.get("id"),
                    "name": group.get("name"),
                    "description": group.get("description") or None,
                    "member_count": len(group.get("members") or []),
                    **(
                        {"is_system_group": True}
                        if group.get("is_system_group")
                        else {}
                    ),
                    **({"deactivated": True} if group.get("deactivated") else {}),
                }
                for group in groups
            ]
        return {"status": "success", "user_groups": groups, "count": len(groups)}
    except Exception as e:
        return internal_error(e)


async def get_user_group_members(
    user_group_id: Annotated[int, Field(gt=0, description="User group ID.")],
    direct_member_only: Annotated[
        bool, Field(description="Exclude members who belong only via a subgroup.")
    ] = False,
) -> dict[str, Any]:
    """Get members of a specific user group (READ-ONLY)."""
    client = get_client()

    try:
        request_data = {"direct_member_only": direct_member_only}
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"user_groups/{user_group_id}/members",
                method="GET",
                request=request_data,
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "user_group_id": user_group_id,
                "members": result.get("members", []),
                "member_count": len(result.get("members", [])),
                "direct_member_only": direct_member_only,
            }
        else:
            return api_error(result, "Failed to get group members")

    except Exception as e:
        return internal_error(e)


async def mute_user(muted_user_id: int) -> dict[str, Any]:
    """Mute a user (affects your own notifications)."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"users/me/muted_users/{muted_user_id}", method="POST", request={}
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "muted_user_id": muted_user_id,
                "action": "muted",
            }
        else:
            return api_error(result, "Failed to mute user")

    except Exception as e:
        return internal_error(e)


async def unmute_user(muted_user_id: int) -> dict[str, Any]:
    """Unmute a user (affects your own notifications)."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"users/me/muted_users/{muted_user_id}", method="DELETE", request={}
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "muted_user_id": muted_user_id,
                "action": "unmuted",
            }
        else:
            return api_error(result, "Failed to unmute user")

    except Exception as e:
        return internal_error(e)


async def resolve_user(
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Full or partial display name to look up.",
        ),
    ],
) -> dict[str, Any]:
    """Resolve a display name to Zulip email. Fuzzy: 'Jaime' -> jaime@org.zulipchat.com"""
    client = get_client()
    user_cache = client.user_cache
    # Warm only the current identity's cache.
    if user_cache.get_users() is None:
        result = await asyncio.to_thread(client.get_users)
        if result.get("result") != "success":
            return api_error(result, "Failed to fetch users")

    resolution = user_cache.resolve_user(name)
    if resolution.get("email"):
        return {"status": "success", **resolution}
    return tool_error(
        f"No single user matches '{name}'",
        "NOT_FOUND",
        recovery_tool="get_users",
        hint="Try the full name, or list members with get_users.",
        query=name,
    )


async def get_user(
    user_id: Annotated[
        int | None, Field(gt=0, description="User ID; used before email.")
    ] = None,
    email: Annotated[
        str | None, Field(max_length=254, description="User email.")
    ] = None,
    include_custom_profile_fields: Annotated[
        bool, Field(description="Add the user's custom profile fields.")
    ] = False,
) -> dict[str, Any]:
    """Look up a user by ID or email."""
    if user_id is not None:
        return await get_user_by_id(
            user_id, include_custom_profile_fields=include_custom_profile_fields
        )
    elif email is not None:
        return await get_user_by_email(
            email, include_custom_profile_fields=include_custom_profile_fields
        )
    else:
        return tool_error("Provide user_id or email")


async def manage_user_mute(
    muted_user_id: UserId,
    action: Annotated[
        Literal["mute", "unmute"],
        Field(description="mute hides the user's messages from you; unmute undoes it."),
    ] = "mute",
) -> dict[str, Any]:
    """Mute or unmute a user."""
    if action == "mute":
        return await mute_user(muted_user_id)
    else:
        return await unmute_user(muted_user_id)


async def set_typing(
    op: Annotated[
        Literal["start", "stop"],
        Field(description="start shows the indicator; stop clears it."),
    ],
    to: Annotated[
        list[int] | None,
        Field(
            min_length=1,
            max_length=100,
            description="User IDs of a direct-message conversation.",
        ),
    ] = None,
    stream_id: Annotated[
        int | None, Field(gt=0, description="Channel ID; use with topic.")
    ] = None,
    topic: Annotated[
        str | None, Field(max_length=60, description="Topic within stream_id.")
    ] = None,
) -> dict[str, Any]:
    """Send a typing start/stop notification to users or a channel topic."""
    if (to is None) == (stream_id is None):
        return tool_error("Provide exactly one of to or stream_id")
    if stream_id is not None and not topic:
        return tool_error("topic is required with stream_id")
    client = get_client()
    try:
        request: dict[str, Any] = {"op": op}
        if to is not None:
            request["type"] = "direct" if client.supports(174) else "private"
            request["to"] = to
        else:
            request["type"] = "channel" if client.supports(248) else "stream"
            request["stream_id"] = stream_id
            request["topic"] = topic
        result = await asyncio.to_thread(
            client.client.call_endpoint, "typing", method="POST", request=request
        )
        if result.get("result") != "success":
            return api_error(result, "Failed to send typing notification")
        return {"status": "success", "op": op}
    except Exception as e:
        return internal_error(e)
