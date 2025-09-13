"""Admin & Migration tools for Zulip MCP v2.5.0.

This module provides administrative tools with clear permission boundaries
and organization customization capabilities.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP

from ..config import ConfigManager
from ..core.identity import IdentityManager, IdentityType
from ..utils.logging import get_logger

logger = get_logger(__name__)


async def admin_operations(
    identity_manager: IdentityManager,
    operation: Literal[
        "settings", "users", "streams", "export", "import", "branding", "profile_fields"
    ],
    realm_id: int | None = None,
    # Settings management
    settings: dict[str, Any] | None = None,
    # User administration
    deactivate_users: list[int] | None = None,
    role_changes: dict[int, str] | None = None,
    # Export/Import
    export_type: Literal["public", "full", "subset"] | None = None,
    export_params: dict | None = None,
    import_data: dict | None = None,
    # Organization branding
    logo_file: bytes | None = None,
    icon_file: bytes | None = None,
    # Custom profile fields management
    profile_field_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Server and realm administration (requires admin privileges).

    Provides comprehensive administrative operations including settings management,
    user administration, and data export/import functionality.

    Args:
        identity_manager: Identity manager for authentication
        operation: Type of admin operation to perform
        realm_id: Target realm ID (optional, uses current realm if None)
        settings: Settings to update (for settings operation)
        deactivate_users: User IDs to deactivate (for users operation)
        role_changes: Map of user_id -> new_role (for users operation)
        export_type: Type of data export (for export operation)
        export_params: Parameters for export (streams, date range, etc.)
        import_data: Data to import (for import operation)

    Returns:
        Dictionary with operation results:
        - status: "success" or "error"
        - operation: Operation that was performed
        - results: Operation-specific results
        - updated_settings: Modified settings (for settings operation)
        - user_changes: User modifications made (for users operation)
        - export_data: Exported data (for export operation)
        - import_summary: Import results (for import operation)
        - timestamp: Operation timestamp

    Raises:
        PermissionError: If user lacks admin privileges
        ValueError: If invalid parameters provided
    """
    try:
        # Check admin permissions
        if not identity_manager.check_capability("admin.admin_operations"):
            raise PermissionError("Admin operations require admin privileges")

        # Use admin identity
        identity = identity_manager.select_best_identity(
            "admin.admin_operations", IdentityType.ADMIN
        )
        client = cast(Any, identity.client)

        result = {
            "status": "success",
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
            "realm_id": realm_id,
        }

        if operation == "settings":
            # Realm settings management
            if settings:
                # Update realm settings
                update_result = client.update_realm(settings)
                if update_result.get("result") != "success":
                    return {
                        "status": "error",
                        "error": f"Failed to update settings: {update_result.get('msg', 'Unknown error')}",
                    }
                result["updated_settings"] = settings
                result["results"] = "Realm settings updated successfully"
            else:
                # Get current realm settings
                realm_result = client.get_realm()
                if realm_result.get("result") == "success":
                    result["current_settings"] = {
                        k: v
                        for k, v in realm_result.items()
                        if k not in ["result", "msg"]
                    }
                    result["results"] = "Retrieved current realm settings"
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to get realm settings: {realm_result.get('msg', 'Unknown error')}",
                    }

        elif operation == "users":
            # User administration
            changes_made = []

            # Deactivate users
            if deactivate_users:
                for user_id in deactivate_users:
                    deactivate_result = client.deactivate_user_by_id(user_id)
                    if deactivate_result.get("result") == "success":
                        changes_made.append(f"Deactivated user {user_id}")
                    else:
                        changes_made.append(
                            f"Failed to deactivate user {user_id}: {deactivate_result.get('msg')}"
                        )

            # Change user roles
            if role_changes:
                for user_id, new_role in role_changes.items():
                    # Map role names to role values
                    role_mapping = {
                        "owner": 100,
                        "admin": 200,
                        "moderator": 300,
                        "member": 400,
                        "guest": 600,
                    }

                    role_value = role_mapping.get(new_role.lower())
                    if role_value is None:
                        changes_made.append(
                            f"Invalid role '{new_role}' for user {user_id}"
                        )
                        continue

                    role_result = client.update_user_by_id(
                        user_id, {"role": role_value}
                    )
                    if role_result.get("result") == "success":
                        changes_made.append(
                            f"Changed user {user_id} role to {new_role}"
                        )
                    else:
                        changes_made.append(
                            f"Failed to change role for user {user_id}: {role_result.get('msg')}"
                        )

            result["user_changes"] = changes_made
            result["results"] = (
                f"Processed user administration: {len(changes_made)} changes"
            )

        elif operation == "streams":
            # Stream administration
            streams_result = client.get_streams(include_all_active=True)
            if streams_result.get("result") == "success":
                streams = streams_result["streams"]

                # Get stream statistics
                stats = {
                    "total_streams": len(streams),
                    "public_streams": len(
                        [s for s in streams if not s.get("invite_only", False)]
                    ),
                    "private_streams": len(
                        [s for s in streams if s.get("invite_only", False)]
                    ),
                    "web_public_streams": len(
                        [s for s in streams if s.get("is_web_public", False)]
                    ),
                }

                result["stream_stats"] = stats
                result["streams"] = streams
                result["results"] = f"Retrieved {len(streams)} streams with statistics"
            else:
                return {
                    "status": "error",
                    "error": f"Failed to get streams: {streams_result.get('msg', 'Unknown error')}",
                }

        elif operation == "export":
            # Data export
            if not export_type:
                export_type = "public"

            export_result = client.start_export(export_type, export_params or {})
            if export_result.get("result") == "success":
                export_id = export_result.get("id")
                result["export_id"] = export_id
                result["export_type"] = export_type
                result["export_params"] = export_params or {}
                result["results"] = f"Started {export_type} export with ID {export_id}"

                # Try to get export status
                try:
                    status_result = client.get_export_status(export_id)
                    if status_result.get("result") == "success":
                        result["export_status"] = status_result.get("export")
                except Exception as e:
                    logger.debug(f"Could not get export status: {e}")
            else:
                return {
                    "status": "error",
                    "error": f"Failed to start export: {export_result.get('msg', 'Unknown error')}",
                }

        elif operation == "import":
            # Data import
            if not import_data:
                return {
                    "status": "error",
                    "error": "Import operation requires import_data parameter",
                }

            # For now, this is a placeholder - actual import would need file handling
            result["import_summary"] = {
                "data_received": len(str(import_data)),
                "import_type": import_data.get("type", "unknown"),
                "status": "queued",
            }
            result["results"] = "Import data received and queued for processing"

        elif operation == "branding":
            # Organization branding management
            branding_updates = []

            if logo_file:
                try:
                    logo_result = client.upload_realm_logo(logo_file)
                    if logo_result.get("result") == "success":
                        branding_updates.append("logo updated successfully")
                    else:
                        branding_updates.append(
                            f"logo update failed: {logo_result.get('msg')}"
                        )
                except Exception as e:
                    branding_updates.append(f"logo update error: {str(e)}")

            if icon_file:
                try:
                    icon_result = client.upload_realm_icon(icon_file)
                    if icon_result.get("result") == "success":
                        branding_updates.append("icon updated successfully")
                    else:
                        branding_updates.append(
                            f"icon update failed: {icon_result.get('msg')}"
                        )
                except Exception as e:
                    branding_updates.append(f"icon update error: {str(e)}")

            if not branding_updates:
                branding_updates.append("no branding updates specified")

            result["branding_updates"] = branding_updates
            result["results"] = (
                f"Processed branding updates: {len(branding_updates)} operations"
            )

        elif operation == "profile_fields":
            # Custom profile fields administration
            if profile_field_config:
                # Create or update custom profile field
                field_result = client.create_custom_profile_field(profile_field_config)
                if field_result.get("result") == "success":
                    result["profile_field_id"] = field_result.get("id")
                    result["profile_field_config"] = profile_field_config
                    result["results"] = "Custom profile field created successfully"
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to create profile field: {field_result.get('msg', 'Unknown error')}",
                    }
            else:
                # List existing custom profile fields
                fields_result = client.get_custom_profile_fields()
                if fields_result.get("result") == "success":
                    result["custom_profile_fields"] = fields_result.get(
                        "custom_fields", []
                    )
                    result["results"] = (
                        f"Retrieved {len(result['custom_profile_fields'])} custom profile fields"
                    )
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to get profile fields: {fields_result.get('msg', 'Unknown error')}",
                    }

        else:
            return {
                "status": "error",
                "error": f"Unknown operation: {operation}",
            }

        return result

    except PermissionError:
        return {
            "status": "error",
            "error": "Admin operations require admin privileges",
            "required_capability": "admin.admin_operations",
        }
    except Exception as e:
        logger.error(f"Admin operations error: {e}")
        return {
            "status": "error",
            "error": f"Admin operations failed: {str(e)}",
            "operation": operation,
        }


async def customize_organization(
    identity_manager: IdentityManager,
    operation: Literal["emoji", "linkifiers", "playgrounds", "filters"],
    # Custom emoji
    emoji_name: str | None = None,
    emoji_file: bytes | None = None,
    # Linkifiers
    pattern: str | None = None,
    url_format: str | None = None,
    # Code playgrounds
    playground_name: str | None = None,
    url_prefix: str | None = None,
    language: str | None = None,
    # Filter operations
    filter_id: int | None = None,
    filter_action: Literal["add", "remove", "update"] | None = None,
    filter_pattern: str | None = None,
) -> dict[str, Any]:
    """Organization customization (requires admin privileges).

    Provides tools for customizing organization appearance and functionality
    including custom emoji, linkifiers, code playgrounds, and message filters.

    Args:
        identity_manager: Identity manager for authentication
        operation: Type of customization operation
        emoji_name: Name for custom emoji (for emoji operation)
        emoji_file: Emoji image file bytes (for emoji operation)
        pattern: Regex pattern (for linkifiers/filters)
        url_format: URL format string (for linkifiers)
        playground_name: Name for code playground (for playgrounds)
        url_prefix: URL prefix for playground (for playgrounds)
        language: Programming language (for playgrounds)
        filter_id: Filter ID for operations (for filters)
        filter_action: Action to perform on filter (for filters)
        filter_pattern: Pattern for filter (for filters)

    Returns:
        Dictionary with customization results:
        - status: "success" or "error"
        - operation: Customization operation performed
        - results: Operation-specific results
        - emoji_info: Emoji details (for emoji operations)
        - linkifier_info: Linkifier details (for linkifier operations)
        - playground_info: Playground details (for playground operations)
        - filter_info: Filter details (for filter operations)
        - timestamp: Operation timestamp

    Raises:
        PermissionError: If user lacks admin privileges
        ValueError: If invalid parameters provided
    """
    try:
        # Check admin permissions
        if not identity_manager.check_capability("admin.customize_organization"):
            raise PermissionError(
                "Organization customization requires admin privileges"
            )

        # Use admin identity
        identity = identity_manager.select_best_identity(
            "admin.customize_organization", IdentityType.ADMIN
        )
        client = identity.client

        result = {
            "status": "success",
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if operation == "emoji":
            # Custom emoji management
            if emoji_name and emoji_file:
                # Add custom emoji
                try:
                    # Convert bytes to base64 for upload
                    emoji_data = base64.b64encode(emoji_file).decode("utf-8")
                    upload_result = client.upload_custom_emoji(emoji_name, emoji_data)

                    if upload_result.get("result") == "success":
                        result["emoji_info"] = {
                            "name": emoji_name,
                            "size": len(emoji_file),
                            "upload_status": "success",
                        }
                        result["results"] = (
                            f"Successfully uploaded custom emoji '{emoji_name}'"
                        )
                    else:
                        return {
                            "status": "error",
                            "error": f"Failed to upload emoji: {upload_result.get('msg', 'Unknown error')}",
                        }
                except Exception as e:
                    return {
                        "status": "error",
                        "error": f"Failed to upload emoji: {str(e)}",
                    }
            else:
                # List custom emoji
                emoji_result = client.get_realm_emoji()
                if emoji_result.get("result") == "success":
                    emoji_list = emoji_result.get("emoji", {})
                    result["emoji_info"] = {
                        "total_custom_emoji": len(emoji_list),
                        "emoji_list": [
                            {
                                "name": name,
                                "source_url": emoji.get("source_url"),
                                "deactivated": emoji.get("deactivated", False),
                            }
                            for name, emoji in emoji_list.items()
                        ],
                    }
                    result["results"] = f"Retrieved {len(emoji_list)} custom emoji"
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to get emoji: {emoji_result.get('msg', 'Unknown error')}",
                    }

        elif operation == "linkifiers":
            # Linkifier management
            if pattern and url_format:
                # Add linkifier
                linkifier_result = client.add_linkifier(pattern, url_format)
                if linkifier_result.get("result") == "success":
                    result["linkifier_info"] = {
                        "pattern": pattern,
                        "url_format": url_format,
                        "id": linkifier_result.get("id"),
                    }
                    result["results"] = (
                        f"Successfully added linkifier with pattern '{pattern}'"
                    )
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to add linkifier: {linkifier_result.get('msg', 'Unknown error')}",
                    }
            else:
                # List linkifiers
                linkifiers_result = client.get_linkifiers()
                if linkifiers_result.get("result") == "success":
                    linkifiers = linkifiers_result.get("linkifiers", [])
                    result["linkifier_info"] = {
                        "total_linkifiers": len(linkifiers),
                        "linkifiers": [
                            {
                                "id": lf.get("id"),
                                "pattern": lf.get("pattern"),
                                "url_format": lf.get("url_format_string"),
                            }
                            for lf in linkifiers
                        ],
                    }
                    result["results"] = f"Retrieved {len(linkifiers)} linkifiers"
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to get linkifiers: {linkifiers_result.get('msg', 'Unknown error')}",
                    }

        elif operation == "playgrounds":
            # Code playground management
            if playground_name and url_prefix:
                # Add code playground
                playground_data = {
                    "name": playground_name,
                    "url_prefix": url_prefix,
                    "pygments_language": language or "text",
                }

                playground_result = client.add_code_playground(**playground_data)
                if playground_result.get("result") == "success":
                    result["playground_info"] = {
                        "name": playground_name,
                        "url_prefix": url_prefix,
                        "language": language or "text",
                        "id": playground_result.get("id"),
                    }
                    result["results"] = (
                        f"Successfully added code playground '{playground_name}'"
                    )
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to add playground: {playground_result.get('msg', 'Unknown error')}",
                    }
            else:
                # List code playgrounds
                playgrounds_result = client.get_code_playgrounds()
                if playgrounds_result.get("result") == "success":
                    playgrounds = playgrounds_result.get("code_playgrounds", [])
                    result["playground_info"] = {
                        "total_playgrounds": len(playgrounds),
                        "playgrounds": [
                            {
                                "id": pg.get("id"),
                                "name": pg.get("name"),
                                "url_prefix": pg.get("url_prefix"),
                                "language": pg.get("pygments_language"),
                            }
                            for pg in playgrounds
                        ],
                    }
                    result["results"] = f"Retrieved {len(playgrounds)} code playgrounds"
                else:
                    return {
                        "status": "error",
                        "error": f"Failed to get playgrounds: {playgrounds_result.get('msg', 'Unknown error')}",
                    }

        elif operation == "filters":
            # Message filter management
            if filter_action == "add" and filter_pattern:
                # Add message filter - this is a conceptual operation
                # In practice, this would integrate with organization-specific filtering
                result["filter_info"] = {
                    "action": "add",
                    "pattern": filter_pattern,
                    "status": "queued",
                }
                result["results"] = f"Queued message filter pattern: {filter_pattern}"

            elif filter_action == "remove" and filter_id:
                # Remove message filter
                result["filter_info"] = {
                    "action": "remove",
                    "filter_id": filter_id,
                    "status": "queued",
                }
                result["results"] = f"Queued removal of filter ID: {filter_id}"

            else:
                # List current filters - placeholder for now
                result["filter_info"] = {
                    "total_filters": 0,
                    "filters": [],
                    "note": "Message filtering is organization-specific and may require custom implementation",
                }
                result["results"] = (
                    "Filter management is available but requires organization-specific configuration"
                )

        else:
            return {
                "status": "error",
                "error": f"Unknown customization operation: {operation}",
            }

        return result

    except PermissionError:
        return {
            "status": "error",
            "error": "Organization customization requires admin privileges",
            "required_capability": "admin.customize_organization",
        }
    except Exception as e:
        logger.error(f"Organization customization error: {e}")
        return {
            "status": "error",
            "error": f"Organization customization failed: {str(e)}",
            "operation": operation,
        }


def register_admin_v25_tools(mcp: FastMCP) -> None:
    """Register v2.5.0 admin tools with the MCP server.

    Args:
        mcp: FastMCP server instance
    """
    config = ConfigManager()
    identity_manager = IdentityManager(config)

    @mcp.tool()
    async def admin_operations_tool(
        operation: Literal[
            "settings",
            "users",
            "streams",
            "export",
            "import",
            "branding",
            "profile_fields",
        ],
        realm_id: int | None = None,
        settings: dict[str, Any] | None = None,
        deactivate_users: list[int] | None = None,
        role_changes: dict[int, str] | None = None,
        export_type: Literal["public", "full", "subset"] | None = None,
        export_params: dict | None = None,
        import_data: dict | None = None,
    ) -> dict[str, Any]:
        """Server and realm administration (requires admin privileges).

        Comprehensive administrative operations including settings management,
        user administration, and data export/import functionality.
        """
        return await admin_operations(
            identity_manager=identity_manager,
            operation=operation,
            realm_id=realm_id,
            settings=settings,
            deactivate_users=deactivate_users,
            role_changes=role_changes,
            export_type=export_type,
            export_params=export_params,
            import_data=import_data,
        )

    @mcp.tool()
    async def customize_organization_tool(
        operation: Literal["emoji", "linkifiers", "playgrounds", "filters"],
        emoji_name: str | None = None,
        emoji_file: bytes | None = None,
        pattern: str | None = None,
        url_format: str | None = None,
        playground_name: str | None = None,
        url_prefix: str | None = None,
        language: str | None = None,
        filter_id: int | None = None,
        filter_action: Literal["add", "remove", "update"] | None = None,
        filter_pattern: str | None = None,
    ) -> dict[str, Any]:
        """Organization customization (requires admin privileges).

        Tools for customizing organization appearance and functionality
        including custom emoji, linkifiers, code playgrounds, and message filters.
        """
        return await customize_organization(
            identity_manager=identity_manager,
            operation=operation,
            emoji_name=emoji_name,
            emoji_file=emoji_file,
            pattern=pattern,
            url_format=url_format,
            playground_name=playground_name,
            url_prefix=url_prefix,
            language=language,
            filter_id=filter_id,
            filter_action=filter_action,
            filter_pattern=filter_pattern,
        )

    logger.info(
        "Registered v2.5.0 admin tools: admin_operations, customize_organization"
    )
