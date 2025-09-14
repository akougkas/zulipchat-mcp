"""User management tools for ZulipChat MCP v2.5.1.

Clean READ-ONLY user operations based on Zulip API endpoints.
No user creation/editing - just reading, searching, and matching users.
"""

import re
from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


def validate_email(email: str) -> bool:
    """Basic email validation."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


async def get_users(
    client_gravatar: bool = True,
    include_custom_profile_fields: bool = False,
    user_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Get all users in organization (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_users()

        if result.get("result") == "success":
            users = result.get("members", [])

            # Filter by user_ids if specified
            if user_ids:
                users = [user for user in users if user.get("user_id") in user_ids]

            return {
                "status": "success",
                "users": users,
                "count": len(users),
                "client_gravatar": client_gravatar,
                "include_custom_profile_fields": include_custom_profile_fields,
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to get users")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_user_by_id(
    user_id: int,
    client_gravatar: bool = True,
    include_custom_profile_fields: bool = False,
) -> dict[str, Any]:
    """Get specific user by ID (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_user_by_id(user_id, include_custom_profile_fields)

        if result.get("result") == "success":
            return {
                "status": "success",
                "user": result.get("user", {}),
            }
        else:
            return {"status": "error", "error": result.get("msg", "User not found")}

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

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_user_by_email(email, include_custom_profile_fields)

        if result.get("result") == "success":
            return {
                "status": "success",
                "user": result.get("user", {}),
            }
        else:
            return {"status": "error", "error": result.get("msg", "User not found")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_own_user() -> dict[str, Any]:
    """Get information about the current user (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.client.call_endpoint("users/me", method="GET", request={})

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
                }
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to get own user")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_user_status(user_id: int) -> dict[str, Any]:
    """Get user's status (away, status text, emoji) (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.client.call_endpoint(f"users/{user_id}/status", method="GET", request={})

        if result.get("result") == "success":
            return {
                "status": "success",
                "user_id": user_id,
                "status": result.get("status", {}),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to get user status")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def update_status(
    status_text: str | None = None,
    emoji_name: str | None = None,
    emoji_code: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] = "unicode_emoji",
) -> dict[str, Any]:
    """Update your own status text and emoji."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        request_data = {}
        if status_text is not None:
            if len(status_text) > 60:
                return {"status": "error", "error": "Status text must be 60 characters or less"}
            request_data["status_text"] = status_text

        if emoji_name is not None:
            request_data["emoji_name"] = emoji_name
        if emoji_code is not None:
            request_data["emoji_code"] = emoji_code
        if emoji_name or emoji_code:
            request_data["reaction_type"] = reaction_type

        if not request_data:
            return {"status": "error", "error": "Must provide status_text, emoji_name, or emoji_code"}

        result = client.client.call_endpoint("users/me/status", method="POST", request=request_data)

        if result.get("result") == "success":
            return {
                "status": "success",
                "updated_status": request_data,
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to update status")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_user_presence(user_id_or_email: str | int) -> dict[str, Any]:
    """Get presence information for a specific user (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.client.call_endpoint(f"users/{user_id_or_email}/presence", method="GET", request={})

        if result.get("result") == "success":
            return {
                "status": "success",
                "user_id_or_email": user_id_or_email,
                "presence": result.get("presence", {}),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to get user presence")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_presence() -> dict[str, Any]:
    """Get presence information for all users in organization (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.client.call_endpoint("realm/presence", method="GET", request={})

        if result.get("result") == "success":
            return {
                "status": "success",
                "server_timestamp": result.get("server_timestamp"),
                "presences": result.get("presences", {}),
                "users_count": len(result.get("presences", {})),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to get presence")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_user_groups(include_deactivated_groups: bool = False) -> dict[str, Any]:
    """Get all user groups in organization (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        request_data = {"include_deactivated_groups": include_deactivated_groups}
        result = client.client.call_endpoint("user_groups", method="GET", request=request_data)

        if result.get("result") == "success":
            return {
                "status": "success",
                "user_groups": result.get("user_groups", []),
                "count": len(result.get("user_groups", [])),
                "include_deactivated": include_deactivated_groups,
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to get user groups")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_user_group_members(
    user_group_id: int,
    direct_member_only: bool = False,
) -> dict[str, Any]:
    """Get members of a specific user group (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        request_data = {"direct_member_only": direct_member_only}
        result = client.client.call_endpoint(
            f"user_groups/{user_group_id}/members", method="GET", request=request_data
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
            return {"status": "error", "error": result.get("msg", "Failed to get group members")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def is_user_group_member(
    user_group_id: int,
    user_id: int,
    direct_member_only: bool = False,
) -> dict[str, Any]:
    """Check if user is member of user group (READ-ONLY)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        request_data = {"direct_member_only": direct_member_only}
        result = client.client.call_endpoint(
            f"user_groups/{user_group_id}/members/{user_id}", method="GET", request=request_data
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "user_group_id": user_group_id,
                "user_id": user_id,
                "is_member": result.get("is_user_group_member", False),
                "direct_member_only": direct_member_only,
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to check group membership")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mute_user(muted_user_id: int) -> dict[str, Any]:
    """Mute a user (affects your own notifications)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.client.call_endpoint(
            f"users/me/muted_users/{muted_user_id}", method="POST", request={}
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "muted_user_id": muted_user_id,
                "action": "muted",
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to mute user")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def unmute_user(muted_user_id: int) -> dict[str, Any]:
    """Unmute a user (affects your own notifications)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.client.call_endpoint(
            f"users/me/muted_users/{muted_user_id}", method="DELETE", request={}
        )

        if result.get("result") == "success":
            return {
                "status": "success",
                "muted_user_id": muted_user_id,
                "action": "unmuted",
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to unmute user")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_users_tools(mcp: FastMCP) -> None:
    """Register clean READ-ONLY user tools with the MCP server."""
    mcp.tool(name="get_users", description="Get all users in organization")(get_users)
    mcp.tool(name="get_user_by_id", description="Get specific user by ID")(get_user_by_id)
    mcp.tool(name="get_user_by_email", description="Get specific user by email")(get_user_by_email)
    mcp.tool(name="get_own_user", description="Get information about current user")(get_own_user)
    mcp.tool(name="get_user_status", description="Get user's status text and emoji")(get_user_status)
    mcp.tool(name="update_status", description="Update your own status text and emoji")(update_status)
    mcp.tool(name="get_user_presence", description="Get presence information for specific user")(get_user_presence)
    mcp.tool(name="get_presence", description="Get presence information for all users")(get_presence)
    mcp.tool(name="get_user_groups", description="Get all user groups in organization")(get_user_groups)
    mcp.tool(name="get_user_group_members", description="Get members of specific user group")(get_user_group_members)
    mcp.tool(name="is_user_group_member", description="Check if user is member of user group")(is_user_group_member)
    mcp.tool(name="mute_user", description="Mute a user for your own notifications")(mute_user)
    mcp.tool(name="unmute_user", description="Unmute a user for your own notifications")(unmute_user)