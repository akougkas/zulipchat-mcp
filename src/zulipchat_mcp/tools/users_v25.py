"""User & Authentication tools for ZulipChat MCP v2.5.0.

This module implements the 3 identity-aware user tools according to PLAN-REFACTOR.md:
1. manage_users() - User operations with identity context
2. switch_identity() - Switch identity context for operations  
3. manage_user_groups() - Manage user groups and permissions

Features:
- Multi-identity support with clear capability boundaries
- User/bot/admin identity switching
- User group management and permissions
- Presence status management
- Custom profile field support
- Enhanced error handling and validation
"""

from __future__ import annotations

from typing import Any, Literal

from ..config import ConfigManager
from ..core.error_handling import get_error_handler
from ..core.identity import IdentityManager, IdentityType
from ..core.validation import ParameterValidator
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error

logger = get_logger(__name__)

# Response type definitions
UserResponse = dict[str, Any]
IdentityResponse = dict[str, Any]
UserGroupResponse = dict[str, Any]

# Global instances
_config_manager: ConfigManager | None = None
_identity_manager: IdentityManager | None = None
_parameter_validator: ParameterValidator | None = None
_error_handler = get_error_handler()


def _get_managers() -> tuple[ConfigManager, IdentityManager, ParameterValidator]:
    """Get or create manager instances."""
    global _config_manager, _identity_manager, _parameter_validator

    if _config_manager is None:
        _config_manager = ConfigManager()

    if _identity_manager is None:
        _identity_manager = IdentityManager(_config_manager)

    if _parameter_validator is None:
        _parameter_validator = ParameterValidator()

    return _config_manager, _identity_manager, _parameter_validator


async def manage_users(
    operation: Literal["list", "get", "update", "presence", "groups", "avatar", "profile_fields"],
    user_id: int | None = None,
    email: str | None = None,
    # Identity context - NEW
    as_bot: bool = False,  # Use bot identity
    as_admin: bool = False,  # Requires admin credentials
    # User updates
    full_name: str | None = None,
    status_text: str | None = None,
    status_emoji: str | None = None,
    # Presence
    status: Literal["active", "idle", "offline"] | None = None,
    client: str = "MCP",
    # Advanced options
    include_custom_profile_fields: bool = False,
    client_gravatar: bool = True,
    # Avatar management
    avatar_file: bytes | None = None,
    # Profile fields
    profile_field_data: dict[str, Any] | None = None,
) -> UserResponse:
    """User operations with identity context.

    This tool provides comprehensive user management with multi-identity support,
    allowing operations as user, bot, or admin with appropriate capability boundaries.

    Args:
        operation: Type of operation to perform
        user_id: Target user ID (for get/update operations)
        email: Target user email (alternative to user_id)
        as_bot: Execute operation using bot identity
        as_admin: Execute operation using admin identity (requires admin access)
        full_name: New full name (for update operation)
        status_text: Status text to set
        status_emoji: Status emoji to set
        status: Presence status to set
        client: Client name for presence updates
        include_custom_profile_fields: Include custom profile data
        client_gravatar: Include gravatar URLs

    Returns:
        UserResponse with operation results and user data

    Examples:
        # List all users (as current identity)
        await manage_users("list")

        # Get user details with admin privileges
        await manage_users("get", email="user@example.com", as_admin=True)

        # Update user status as bot
        await manage_users("update", user_id=123, status_text="Working on project", as_bot=True)

        # Set presence status
        await manage_users("presence", status="active", client="Mobile App")

        # Update avatar
        await manage_users("avatar", avatar_file=avatar_bytes)

        # Update custom profile fields
        await manage_users("profile_fields", profile_field_data={"department": "Engineering"})
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "users.manage_users"}):
        with LogContext(logger, tool="manage_users", operation=operation, as_bot=as_bot, as_admin=as_admin):
            track_tool_call("users.manage_users")

            try:
                config, identity_manager, validator = _get_managers()

                # Validate mutually exclusive identity options
                if as_bot and as_admin:
                    return {
                        "status": "error",
                        "error": "Cannot use both as_bot and as_admin simultaneously"
                    }

                # Operation-specific validation
                if operation in ["get", "update"] and not user_id and not email:
                    return {
                        "status": "error",
                        "error": "user_id or email required for get/update operations"
                    }

                # Ensure user_id is properly initialized for update operations
                current_user_id = user_id

                if operation == "update" and not any([full_name, status_text, status_emoji]):
                    return {
                        "status": "error",
                        "error": "At least one update field required (full_name, status_text, status_emoji)"
                    }

                if operation == "presence" and not status:
                    return {
                        "status": "error",
                        "error": "status required for presence operation"
                    }

                # Select appropriate identity
                preferred_identity = None
                if as_admin:
                    preferred_identity = IdentityType.ADMIN
                elif as_bot:
                    preferred_identity = IdentityType.BOT

                # Execute with appropriate identity and error handling
                async def _execute_user_operation(client, params):
                    # Use a local variable to avoid Python closure scoping issues
                    resolved_user_id = current_user_id
                    if operation == "list":
                        # Use ZulipClientWrapper get_users with automatic caching
                        result = client.get_users()
                        # Note: ZulipClientWrapper handles caching automatically for better performance

                        if result.get("result") == "success":
                            return {
                                "status": "success",
                                "operation": "list",
                                "users": result.get("members", []),
                                "count": len(result.get("members", [])),
                                "identity_used": identity_manager.get_current_identity().type.value
                            }

                    elif operation == "get":
                        # Get specific user
                        if resolved_user_id:
                            result = client.get_user_by_id(resolved_user_id, include_custom_profile_fields=include_custom_profile_fields)
                        else:
                            result = client.get_user_by_email(email, include_custom_profile_fields=include_custom_profile_fields)

                        if result.get("result") == "success":
                            return {
                                "status": "success",
                                "operation": "get",
                                "user": result.get("user", {}),
                                "identity_used": identity_manager.get_current_identity().type.value
                            }

                    elif operation == "update":
                        # Update user profile
                        if not resolved_user_id:
                            # Get user_id from email
                            user_result = client.get_user_by_email(email)
                            if user_result.get("result") != "success":
                                return {
                                    "status": "error",
                                    "error": f"User not found: {email}"
                                }
                            resolved_user_id = user_result["user"]["user_id"]

                        update_data = {}
                        if full_name:
                            update_data["full_name"] = full_name
                        if status_text is not None:
                            update_data["status_text"] = status_text
                        if status_emoji is not None:
                            update_data["status_emoji"] = status_emoji

                        result = client.update_user(resolved_user_id, **update_data)

                        if result.get("result") == "success":
                            return {
                                "status": "success",
                                "operation": "update",
                                "user_id": resolved_user_id,
                                "updated_fields": list(update_data.keys()),
                                "identity_used": identity_manager.get_current_identity().type.value
                            }

                    elif operation == "presence":
                        # Update presence status
                        result = client.update_presence(status=status, ping_only=False, new_user_input=True)

                        if result.get("result") == "success":
                            return {
                                "status": "success",
                                "operation": "presence",
                                "new_status": status,
                                "client": client,
                                "identity_used": identity_manager.get_current_identity().type.value
                            }

                    elif operation == "groups":
                        # Get user group memberships
                        result = client.get_user_groups()

                        if result.get("result") == "success":
                            groups = result.get("user_groups", [])
                            current_profile_user_id = identity_manager.get_current_identity().client.get_profile()["user_id"]

                            # Filter groups where user is a member
                            user_groups = []
                            for group in groups:
                                if current_profile_user_id in group.get("members", []):
                                    user_groups.append(group)

                            return {
                                "status": "success",
                                "operation": "groups",
                                "user_groups": user_groups,
                                "all_groups": groups,
                                "identity_used": identity_manager.get_current_identity().type.value
                            }

                    elif operation == "avatar":
                        # Avatar management
                        if avatar_file:
                            # Upload new avatar
                            result = client.upload_avatar(avatar_file)
                            if result.get("result") == "success":
                                return {
                                    "status": "success",
                                    "operation": "avatar",
                                    "message": "Avatar updated successfully",
                                    "identity_used": identity_manager.get_current_identity().type.value
                                }
                        else:
                            return {
                                "status": "error",
                                "error": "avatar_file is required for avatar operation"
                            }

                    elif operation == "profile_fields":
                        # Custom profile fields management
                        if profile_field_data:
                            # Update custom profile fields
                            result = client.update_profile_fields(profile_field_data)
                            if result.get("result") == "success":
                                return {
                                    "status": "success",
                                    "operation": "profile_fields",
                                    "updated_fields": list(profile_field_data.keys()),
                                    "identity_used": identity_manager.get_current_identity().type.value
                                }
                        else:
                            # Get current custom profile fields
                            result = client.get_custom_profile_fields()
                            if result.get("result") == "success":
                                return {
                                    "status": "success",
                                    "operation": "profile_fields",
                                    "available_fields": result.get("custom_fields", []),
                                    "identity_used": identity_manager.get_current_identity().type.value
                                }

                    # Handle API errors
                    return {
                        "status": "error",
                        "error": result.get("msg", "Unknown error occurred"),
                        "operation": operation,
                        "code": result.get("code")
                    }

                # Execute with identity management and error handling
                result = await identity_manager.execute_with_identity(
                    "users.manage_users",
                    {"operation": operation},
                    _execute_user_operation,
                    preferred_identity
                )

                logger.info(f"User operation {operation} completed successfully")
                return result

            except Exception as e:
                error_msg = f"Failed to execute user operation {operation}: {str(e)}"
                logger.error(error_msg)
                track_tool_error("users.manage_users", str(e))

                return {
                    "status": "error",
                    "error": error_msg,
                    "operation": operation
                }


async def switch_identity(
    identity: Literal["user", "bot", "admin"],
    persist: bool = False,  # Temporary switch
    validate: bool = True,  # Check credentials
) -> IdentityResponse:
    """Switch identity context for operations.

    This tool allows switching between user, bot, and admin identities with
    proper validation and capability management.

    Args:
        identity: Target identity type to switch to
        persist: If True, make this the default identity for future operations
        validate: If True, validate the target identity credentials

    Returns:
        IdentityResponse with current identity information and capabilities

    Examples:
        # Temporarily switch to bot identity
        await switch_identity("bot", persist=False)

        # Permanently switch to admin identity with validation
        await switch_identity("admin", persist=True, validate=True)

        # Quick switch without credential validation
        await switch_identity("user", validate=False)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "users.switch_identity"}):
        with LogContext(logger, tool="switch_identity", target_identity=identity, persist=persist):
            track_tool_call("users.switch_identity")

            try:
                config, identity_manager, validator = _get_managers()

                # Convert string to IdentityType
                try:
                    target_type = IdentityType(identity)
                except ValueError:
                    return {
                        "status": "error",
                        "error": f"Invalid identity type: {identity}. Must be one of: user, bot, admin"
                    }

                # Attempt to switch identity
                result = identity_manager.switch_identity(
                    target_type,
                    persist=persist,
                    validate=validate
                )

                # Get available identities for response
                available_identities = identity_manager.get_available_identities()

                logger.info(f"Successfully switched to {identity} identity (persist={persist})")

                return {
                    "status": "success",
                    "switched_to": result["identity"],
                    "previous_identity": available_identities.get("current"),
                    "persistent": result["persistent"],
                    "capabilities": result["capabilities"],
                    "email": result["email"],
                    "display_name": result["display_name"],
                    "name": result["name"],
                    "available_identities": available_identities["available"]
                }

            except Exception as e:
                error_msg = f"Failed to switch to {identity} identity: {str(e)}"
                logger.error(error_msg)
                track_tool_error("users.switch_identity", str(e))

                return {
                    "status": "error",
                    "error": error_msg,
                    "target_identity": identity
                }


async def manage_user_groups(
    action: Literal["create", "update", "delete", "add_members", "remove_members"],
    group_name: str | None = None,
    group_id: int | None = None,
    description: str | None = None,
    members: list[int] | None = None,
) -> UserGroupResponse:
    """Manage user groups and permissions.

    This tool provides comprehensive user group management including creation,
    modification, deletion, and member management.

    Args:
        action: Action to perform on user groups
        group_name: Name of the user group (required for create, optional for others)
        group_id: ID of the user group (alternative to group_name)
        description: Description for the group (used in create/update)
        members: List of user IDs for member operations

    Returns:
        UserGroupResponse with operation results and group information

    Examples:
        # Create new user group
        await manage_user_groups("create", group_name="developers", 
                                description="Development team", members=[1, 2, 3])

        # Add members to existing group
        await manage_user_groups("add_members", group_id=5, members=[4, 5])

        # Update group description
        await manage_user_groups("update", group_name="developers", 
                                description="Software development team")

        # Remove members from group
        await manage_user_groups("remove_members", group_id=5, members=[3])

        # Delete group
        await manage_user_groups("delete", group_id=5)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "users.manage_user_groups"}):
        with LogContext(logger, tool="manage_user_groups", action=action, group_name=group_name):
            track_tool_call("users.manage_user_groups")

            try:
                config, identity_manager, validator = _get_managers()

                # Validation
                if action == "create" and not group_name:
                    return {
                        "status": "error",
                        "error": "group_name is required for create action"
                    }

                if action in ["update", "delete", "add_members", "remove_members"] and not group_name and not group_id:
                    return {
                        "status": "error",
                        "error": "group_name or group_id is required for this action"
                    }

                if action in ["add_members", "remove_members"] and not members:
                    return {
                        "status": "error",
                        "error": "members list is required for member operations"
                    }

                # This operation typically requires admin privileges
                preferred_identity = IdentityType.ADMIN

                # Execute with appropriate identity and error handling
                async def _execute_group_operation(client, params):
                    if action == "create":
                        # Create new user group
                        request_data = {
                            "name": group_name,
                            "description": description or f"User group: {group_name}",
                            "members": members or []
                        }
                        result = client.create_user_group(request_data)

                        if result.get("result") == "success":
                            return {
                                "status": "success",
                                "action": "create",
                                "group_name": group_name,
                                "group_id": result.get("id"),
                                "members_added": len(members or []),
                                "description": description
                            }

                    elif action in ["update", "delete", "add_members", "remove_members"]:
                        # First, resolve group_id if only group_name provided
                        if not group_id and group_name:
                            groups_result = client.get_user_groups()
                            if groups_result.get("result") != "success":
                                return {
                                    "status": "error",
                                    "error": "Failed to retrieve user groups"
                                }

                            target_group_id = None
                            for group in groups_result.get("user_groups", []):
                                if group["name"] == group_name:
                                    target_group_id = group["id"]
                                    break

                            if not target_group_id:
                                return {
                                    "status": "error",
                                    "error": f"User group '{group_name}' not found"
                                }
                        else:
                            target_group_id = group_id

                        if action == "update":
                            # Update group description
                            request_data = {}
                            if description is not None:
                                request_data["description"] = description
                            if group_name and group_name != group_name:  # Allow renaming
                                request_data["name"] = group_name

                            result = client.update_user_group(target_group_id, request_data)

                            if result.get("result") == "success":
                                return {
                                    "status": "success",
                                    "action": "update",
                                    "group_id": target_group_id,
                                    "updated_fields": list(request_data.keys())
                                }

                        elif action == "delete":
                            # Delete user group
                            result = client.remove_user_group(target_group_id)

                            if result.get("result") == "success":
                                return {
                                    "status": "success",
                                    "action": "delete",
                                    "group_id": target_group_id,
                                    "group_name": group_name
                                }

                        elif action == "add_members":
                            # Add members to group
                            result = client.update_user_group_members(target_group_id, add=members)

                            if result.get("result") == "success":
                                return {
                                    "status": "success",
                                    "action": "add_members",
                                    "group_id": target_group_id,
                                    "members_added": members,
                                    "count": len(members)
                                }

                        elif action == "remove_members":
                            # Remove members from group
                            result = client.update_user_group_members(target_group_id, delete=members)

                            if result.get("result") == "success":
                                return {
                                    "status": "success",
                                    "action": "remove_members",
                                    "group_id": target_group_id,
                                    "members_removed": members,
                                    "count": len(members)
                                }

                    # Handle API errors
                    return {
                        "status": "error",
                        "error": result.get("msg", "Unknown error occurred"),
                        "action": action,
                        "code": result.get("code")
                    }

                # Execute with identity management and error handling
                result = await identity_manager.execute_with_identity(
                    "users.manage_user_groups",
                    {"action": action},
                    _execute_group_operation,
                    preferred_identity
                )

                logger.info(f"User group operation {action} completed successfully")
                return result

            except Exception as e:
                error_msg = f"Failed to execute user group operation {action}: {str(e)}"
                logger.error(error_msg)
                track_tool_error("users.manage_user_groups", str(e))

                return {
                    "status": "error",
                    "error": error_msg,
                    "action": action
                }


def register_users_v25_tools(mcp: Any) -> None:
    """Register all users v2.5 tools with the MCP server.

    Args:
        mcp: FastMCP instance to register tools on
    """
    mcp.tool(description="User operations with identity context")(manage_users)
    mcp.tool(description="Switch identity context for operations")(switch_identity)
    mcp.tool(description="Manage user groups and permissions")(manage_user_groups)
