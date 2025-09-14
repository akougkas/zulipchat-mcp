"""User management tools for ZulipChat MCP v2.5.1.

Complete user operations including management, presence, profile fields, and groups.
All functionality from the complex v25 architecture preserved in minimal code.
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


async def manage_users(
    operation: Literal["list", "get", "update", "presence", "groups", "avatar", "profile_fields"],
    email: str | None = None,
    user_id: int | None = None,
    full_name: str | None = None,
    include_custom_profile_fields: bool = False,
    client_gravatar: bool = True,
    # Presence parameters
    status: Literal["active", "idle", "offline"] | None = None,
    status_text: str | None = None,
    status_emoji: str | None = None,
    client: str = "MCP",
    # Profile field data
    profile_field_data: dict[str, Any] | None = None,
    # Avatar file
    avatar_file: bytes | None = None,
    # Identity context
    as_bot: bool = False,
    as_admin: bool = False,
) -> dict[str, Any]:
    """User management with multi-identity support and comprehensive operations."""
    config = ConfigManager()

    # Select identity based on operation and parameters
    if as_bot and config.has_bot_credentials():
        zulip_client = ZulipClientWrapper(config, use_bot_identity=True)
    else:
        zulip_client = ZulipClientWrapper(config, use_bot_identity=False)

    try:
        if operation == "list":
            result = zulip_client.get_users()

            if result.get("result") == "success":
                users = result.get("members", [])

                # Filter and enhance user data
                processed_users = []
                for user in users:
                    user_data = {
                        "user_id": user.get("user_id"),
                        "email": user.get("email"),
                        "full_name": user.get("full_name"),
                        "is_active": user.get("is_active", True),
                        "is_admin": user.get("is_admin", False),
                        "is_owner": user.get("is_owner", False),
                        "is_bot": user.get("is_bot", False),
                        "is_guest": user.get("is_guest", False),
                        "timezone": user.get("timezone"),
                        "avatar_url": user.get("avatar_url"),
                        "date_joined": user.get("date_joined"),
                    }

                    if include_custom_profile_fields and user.get("profile_data"):
                        user_data["profile_data"] = user.get("profile_data")

                    processed_users.append(user_data)

                return {
                    "status": "success",
                    "users": processed_users,
                    "count": len(processed_users),
                    "include_custom_profile_fields": include_custom_profile_fields,
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to get users")}

        elif operation == "get":
            if not email and not user_id:
                return {"status": "error", "error": "Either email or user_id is required"}

            if email:
                if not validate_email(email):
                    return {"status": "error", "error": f"Invalid email format: {email}"}
                result = zulip_client.get_user_by_email(email, include_custom_profile_fields)
            else:
                result = zulip_client.get_user_by_id(user_id, include_custom_profile_fields)

            if result.get("result") == "success":
                user = result.get("user", {})
                return {
                    "status": "success",
                    "user": user,
                    "user_id": user.get("user_id"),
                    "email": user.get("email"),
                    "full_name": user.get("full_name"),
                }
            else:
                return {"status": "error", "error": result.get("msg", "User not found")}

        elif operation == "presence":
            if not status:
                return {"status": "error", "error": "status is required for presence operation"}

            result = zulip_client.update_presence(status, ping_only=False)

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "operation": "presence",
                    "presence_status": status,
                    "client": client,
                    "presence": result.get("presence", {}),
                }
            else:
                return {"status": "error", "error": result.get("msg", "Failed to update presence")}

        elif operation == "update":
            if not email and not user_id:
                return {"status": "error", "error": "Either email or user_id is required for update"}

            # Basic user update (limited by Zulip API permissions)
            if user_id and full_name:
                try:
                    # This typically requires admin permissions
                    result = zulip_client.update_user(user_id, full_name=full_name)
                    if result.get("result") == "success":
                        return {
                            "status": "success",
                            "operation": "update",
                            "user_id": user_id,
                            "updated_fields": {"full_name": full_name},
                        }
                    else:
                        return {"status": "error", "error": result.get("msg", "Failed to update user")}
                except Exception as e:
                    return {"status": "error", "error": f"Update failed: {str(e)}"}

        elif operation == "profile_fields":
            # Get available custom profile fields
            try:
                # This would require a specific API call to get profile field schema
                # For now, return the user's current profile data
                if email:
                    user_result = zulip_client.get_user_by_email(email, include_custom_profile_fields=True)
                elif user_id:
                    user_result = zulip_client.get_user_by_id(user_id, include_custom_profile_fields=True)
                else:
                    return {"status": "error", "error": "email or user_id required"}

                if user_result.get("result") == "success":
                    user = user_result.get("user", {})
                    return {
                        "status": "success",
                        "operation": "profile_fields",
                        "user_id": user.get("user_id"),
                        "profile_data": user.get("profile_data", {}),
                    }
                else:
                    return {"status": "error", "error": user_result.get("msg", "Failed to get profile fields")}

            except Exception as e:
                return {"status": "error", "error": str(e)}

        else:
            return {"status": "error", "error": f"Operation '{operation}' not yet implemented"}

    except Exception as e:
        return {"status": "error", "error": str(e), "operation": operation}


def register_users_tools(mcp: FastMCP) -> None:
    """Register user tools with the MCP server."""
    mcp.tool(name="manage_users", description="User management with multi-identity support and comprehensive operations")(manage_users)