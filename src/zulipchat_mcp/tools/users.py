"""User management tools for ZulipChat MCP v0.4.0.

Clean READ-ONLY user operations based on Zulip API endpoints.
No user creation/editing - just reading, searching, and matching users.
"""

import asyncio
import re
from typing import Any, Literal

from ..config import get_client
from ..core.api_errors import api_error


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


async def get_users(
    client_gravatar: bool = True,
    include_custom_profile_fields: bool = False,
    user_ids: list[int] | None = None,
    verbose: bool = False,
    role: Literal["owner", "admin", "moderator", "member", "guest"] | None = None,
) -> dict[str, Any]:
    """Organization members; role narrows to one role. Set verbose for raw objects."""
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
            if not verbose:
                users = [_user_row(user) for user in users]
            return {"status": "success", "users": users, "count": len(users)}
        else:
            return api_error(result, "Failed to get users")

    except Exception as e:
        return {"status": "error", "error": str(e)}


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
        return {"status": "error", "error": str(e)}


async def get_user_by_email(
    email: str,
    client_gravatar: bool = True,
    include_custom_profile_fields: bool = False,
) -> dict[str, Any]:
    """Get specific user by email (READ-ONLY)."""
    if not validate_email(email):
        return {"status": "error", "error": f"Invalid email format: {email}"}

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
        return {"status": "error", "error": str(e)}


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
        return {"status": "error", "error": str(e)}


async def get_user_status(user_id: int) -> dict[str, Any]:
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
        return {"status": "error", "error": str(e)}


async def update_status(
    status_text: str | None = None,
    emoji_name: str | None = None,
    emoji_code: str | None = None,
    reaction_type: Literal[
        "unicode_emoji", "realm_emoji", "zulip_extra_emoji"
    ] = "unicode_emoji",
) -> dict[str, Any]:
    """Update your own status text and emoji."""
    client = get_client()

    try:
        request_data = {}
        if status_text is not None:
            if len(status_text) > 60:
                return {
                    "status": "error",
                    "error": "Status text must be 60 characters or less",
                }
            request_data["status_text"] = status_text

        if emoji_name is not None:
            request_data["emoji_name"] = emoji_name
        if emoji_code is not None:
            request_data["emoji_code"] = emoji_code
        if emoji_name or emoji_code:
            request_data["reaction_type"] = reaction_type

        if not request_data:
            return {
                "status": "error",
                "error": "Must provide status_text, emoji_name, or emoji_code",
            }

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
        return {"status": "error", "error": str(e)}


async def get_user_presence(user_id_or_email: str | int) -> dict[str, Any]:
    """Get presence information for a specific user (READ-ONLY)."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                f"users/{user_id_or_email}/presence", method="GET", request={}
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
        return {"status": "error", "error": str(e)}


async def get_presence() -> dict[str, Any]:
    """Get presence information for all users in organization (READ-ONLY)."""
    client = get_client()

    try:
        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "realm/presence", method="GET", request={}
            )
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "server_timestamp": result.get("server_timestamp"),
                "presences": result.get("presences", {}),
                "users_count": len(result.get("presences", {})),
            }
        else:
            return api_error(result, "Failed to get presence")

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_user_groups(
    include_deactivated_groups: bool = False, verbose: bool = False
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
        return {"status": "error", "error": str(e)}


async def get_user_group_members(
    user_group_id: int,
    direct_member_only: bool = False,
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
        return {"status": "error", "error": str(e)}


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
        return {"status": "error", "error": str(e)}


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
        return {"status": "error", "error": str(e)}


async def resolve_user(name: str) -> dict[str, Any]:
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
    return {
        "status": "not_found",
        "query": name,
        "suggestion": "Try full name or email",
    }


async def get_user(
    user_id: int | None = None,
    email: str | None = None,
    include_custom_profile_fields: bool = False,
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
        return {"status": "error", "error": "Provide user_id or email"}


async def manage_user_mute(
    muted_user_id: int,
    action: Literal["mute", "unmute"] = "mute",
) -> dict[str, Any]:
    """Mute or unmute a user."""
    if action == "mute":
        return await mute_user(muted_user_id)
    else:
        return await unmute_user(muted_user_id)


async def set_typing(
    op: Literal["start", "stop"],
    to: list[int] | None = None,
    stream_id: int | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Send a typing start/stop notification to users or a channel topic."""
    if (to is None) == (stream_id is None):
        return {"status": "error", "error": "Provide exactly one of to or stream_id"}
    if stream_id is not None and not topic:
        return {"status": "error", "error": "topic is required with stream_id"}
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
        return {"status": "error", "error": str(e)}
