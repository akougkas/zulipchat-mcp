"""Migration and backward compatibility layer for Zulip MCP v2.5.0.

This module provides backward compatibility for existing tools while
migrating to the new consolidated architecture.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..utils.logging import get_logger

logger = get_logger(__name__)


class MigrationStatus(Enum):
    """Status of tool migration."""

    ACTIVE = "active"  # Old tool still in use
    DEPRECATED = "deprecated"  # Old tool deprecated, new tool available
    MIGRATED = "migrated"  # Fully migrated to new tool
    REMOVED = "removed"  # Old tool removed


@dataclass
class ToolMigration:
    """Migration information for a tool."""

    old_name: str
    new_name: str
    new_params: Dict[str, Any]  # Default parameters for new tool
    param_mapping: Dict[str, str]  # Map old param names to new
    status: MigrationStatus
    deprecated_since: Optional[str] = None  # Version when deprecated
    removal_version: Optional[str] = None  # Version when will be removed
    migration_notes: Optional[str] = None


class MigrationManager:
    """Manages tool migrations and backward compatibility."""

    # Tool migration mappings
    TOOL_MIGRATIONS = {
        # Messaging consolidation
        "send_message": ToolMigration(
            old_name="send_message",
            new_name="messaging.message",
            new_params={"operation": "send"},
            param_mapping={
                "message_type": "type",
                "stream": "to",
                "private_recipients": "to",
                "subject": "topic",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
            migration_notes="Use messaging.message with operation='send'",
        ),
        "get_messages": ToolMigration(
            old_name="get_messages",
            new_name="messaging.search_messages",
            new_params={},
            param_mapping={
                "stream_name": None,  # Needs conversion to narrow
                "hours_back": None,  # Needs conversion to narrow
                "limit": "num_before",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
            migration_notes="Use messaging.search_messages with narrow filters",
        ),
        "edit_message": ToolMigration(
            old_name="edit_message",
            new_name="messaging.edit_message",
            new_params={},
            param_mapping={
                "subject": "topic",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        "add_reaction": ToolMigration(
            old_name="add_reaction",
            new_name="messaging.bulk_operations",
            new_params={"operation": "add_flag"},
            param_mapping={
                "emoji_name": "flag",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        # Stream consolidation
        "get_streams": ToolMigration(
            old_name="get_streams",
            new_name="streams.manage_streams",
            new_params={"operation": "list"},
            param_mapping={},
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        "create_stream": ToolMigration(
            old_name="create_stream",
            new_name="streams.manage_streams",
            new_params={"operation": "create"},
            param_mapping={
                "stream_name": "stream_names",
                "description": "description",  # Direct mapping
                "invite_only": "invite_only",  # Direct mapping
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        "rename_stream": ToolMigration(
            old_name="rename_stream",
            new_name="streams.manage_streams",
            new_params={"operation": "update"},
            param_mapping={
                "old_name": "stream_names",
                "new_name": "new_name",  # Direct mapping
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        "archive_stream": ToolMigration(
            old_name="archive_stream",
            new_name="streams.manage_streams",
            new_params={"operation": "delete"},
            param_mapping={
                "stream_name": "stream_names",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        # Agent system → Events
        "register_agent": ToolMigration(
            old_name="register_agent",
            new_name="events.register_events",
            new_params={"event_types": ["message"]},
            param_mapping={
                "agent_id": None,  # No direct mapping
                "agent_type": None,
                "project_name": None,
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
            migration_notes="Agent system replaced with stateless event streaming",
        ),
        "agent_message": ToolMigration(
            old_name="agent_message",
            new_name="messaging.message",
            new_params={"operation": "send", "as_bot": True},
            param_mapping={
                "message": "content",
                "stream": "to",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        "poll_agent_events": ToolMigration(
            old_name="poll_agent_events",
            new_name="events.get_events",
            new_params={},
            param_mapping={
                "agent_id": "queue_id",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        # Search enhancement
        "search_messages": ToolMigration(
            old_name="search_messages",
            new_name="search.advanced_search",
            new_params={"search_type": ["messages"]},
            param_mapping={
                "query": "query",
                "num_results": "limit",
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        "get_daily_summary": ToolMigration(
            old_name="get_daily_summary",
            new_name="search.analytics",
            new_params={"metric": "activity"},
            param_mapping={
                "streams": "narrow",  # Needs conversion
                "hours_back": "time_range",  # Needs conversion
            },
            status=MigrationStatus.DEPRECATED,
            deprecated_since="2.5.0",
            removal_version="3.0.0",
        ),
        # Administration - New in v2.5.0 (no migrations needed)
        # These are new consolidated admin tools with clear permission boundaries
    }

    def __init__(self):
        """Initialize migration manager."""
        self.deprecation_warnings: Set[str] = set()
        self.migration_stats: Dict[str, int] = {}
        self.disabled_tools: Set[str] = set()

    def migrate_tool_call(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """Migrate a tool call to the new format.

        Args:
            tool_name: Old tool name
            params: Tool parameters

        Returns:
            Tuple of (new_tool_name, migrated_params)

        Raises:
            ValueError: If tool has been removed
        """
        migration = self.TOOL_MIGRATIONS.get(tool_name)
        if not migration:
            # Not a migrated tool, return as-is
            return tool_name, params

        # Check migration status
        if migration.status == MigrationStatus.REMOVED:
            raise ValueError(
                f"Tool '{tool_name}' has been removed. {migration.migration_notes or ''}"
            )

        # Issue deprecation warning (once per session)
        if migration.status == MigrationStatus.DEPRECATED:
            self._issue_deprecation_warning(migration)

        # Migrate parameters
        new_params = migration.new_params.copy()
        migrated_params = self._migrate_params(params, migration.param_mapping)
        new_params.update(migrated_params)

        # Special handling for complex migrations
        new_params = self._handle_special_migrations(tool_name, params, new_params)

        # Track migration
        self._track_migration(tool_name, migration.new_name)

        return migration.new_name, new_params

    def _migrate_params(
        self, params: Dict[str, Any], mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Migrate parameters based on mapping.

        Args:
            params: Original parameters
            mapping: Parameter name mapping

        Returns:
            Migrated parameters
        """
        migrated = {}
        for old_name, old_value in params.items():
            if old_name in mapping:
                new_name = mapping[old_name]
                if new_name is None:
                    # Explicitly mapped to None means it needs special handling
                    continue
                else:
                    # Simple direct mapping only - no nested complexity
                    migrated[new_name] = old_value
            else:
                # No mapping defined, preserve the parameter as-is
                migrated[old_name] = old_value
        return migrated

    def _handle_special_migrations(
        self, old_tool: str, old_params: Dict[str, Any], new_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle special migration cases that need custom logic.

        Args:
            old_tool: Old tool name
            old_params: Original parameters
            new_params: Partially migrated parameters

        Returns:
            Fully migrated parameters
        """
        # Handle get_messages migration
        if old_tool == "get_messages":
            narrow = []
            if "stream_name" in old_params:
                narrow.append({"operator": "stream", "operand": old_params["stream_name"]})
            if "hours_back" in old_params:
                from datetime import datetime, timedelta

                after = datetime.now() - timedelta(hours=old_params["hours_back"])
                narrow.append(
                    {"operator": "search", "operand": f"after:{after.isoformat()}"}
                )
            new_params["narrow"] = narrow

        # Handle create_stream migration - simplified
        elif old_tool == "create_stream":
            if "stream_name" in old_params:
                new_params["stream_names"] = [old_params["stream_name"]]

        # Handle get_daily_summary migration
        elif old_tool == "get_daily_summary":
            if "streams" in old_params:
                # Convert stream list to narrow filters
                narrow = []
                for stream in old_params["streams"]:
                    narrow.append({"operator": "stream", "operand": stream})
                new_params["narrow"] = narrow
            if "hours_back" in old_params:
                new_params["time_range"] = {"hours": old_params["hours_back"]}

        return new_params

    def _issue_deprecation_warning(self, migration: ToolMigration):
        """Issue a deprecation warning for a tool.

        Args:
            migration: Tool migration information
        """
        if migration.old_name not in self.deprecation_warnings:
            message = (
                f"Tool '{migration.old_name}' is deprecated since v{migration.deprecated_since}. "
                f"Use '{migration.new_name}' instead."
            )
            if migration.removal_version:
                message += f" Will be removed in v{migration.removal_version}."
            if migration.migration_notes:
                message += f" {migration.migration_notes}"

            warnings.warn(message, DeprecationWarning, stacklevel=3)
            logger.warning(message)
            self.deprecation_warnings.add(migration.old_name)

    def _track_migration(self, old_tool: str, new_tool: str):
        """Track migration statistics.

        Args:
            old_tool: Old tool name
            new_tool: New tool name
        """
        key = f"{old_tool}->{new_tool}"
        self.migration_stats[key] = self.migration_stats.get(key, 0) + 1

    def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status and statistics.

        Returns:
            Migration status information
        """
        status = {
            "deprecated_tools": [],
            "removed_tools": [],
            "migration_stats": self.migration_stats,
            "warnings_issued": list(self.deprecation_warnings),
        }

        for tool_name, migration in self.TOOL_MIGRATIONS.items():
            if migration.status == MigrationStatus.DEPRECATED:
                status["deprecated_tools"].append(
                    {
                        "old": tool_name,
                        "new": migration.new_name,
                        "removal_version": migration.removal_version,
                    }
                )
            elif migration.status == MigrationStatus.REMOVED:
                status["removed_tools"].append(tool_name)

        return status

    def disable_legacy_tool(self, tool_name: str):
        """Disable a legacy tool to force migration.

        Args:
            tool_name: Tool to disable
        """
        self.disabled_tools.add(tool_name)
        logger.info(f"Disabled legacy tool: {tool_name}")

    def is_tool_disabled(self, tool_name: str) -> bool:
        """Check if a tool has been disabled.

        Args:
            tool_name: Tool name to check

        Returns:
            True if tool is disabled
        """
        return tool_name in self.disabled_tools

    def create_compatibility_wrapper(
        self, new_tool_func: Callable
    ) -> Callable:
        """Create a wrapper that provides backward compatibility.

        Args:
            new_tool_func: New tool function

        Returns:
            Wrapped function with compatibility layer
        """

        async def wrapper(tool_name: str, params: Dict[str, Any]) -> Any:
            # Check if disabled
            if self.is_tool_disabled(tool_name):
                raise ValueError(
                    f"Tool '{tool_name}' has been disabled. Please migrate to the new API."
                )

            # Migrate if needed
            new_name, new_params = self.migrate_tool_call(tool_name, params)

            # Call new tool
            return await new_tool_func(new_name, new_params)

        return wrapper

    def get_migration_guide(self, tool_name: Optional[str] = None) -> str:
        """Get migration guide for tools.

        Args:
            tool_name: Specific tool to get guide for (all if None)

        Returns:
            Migration guide text
        """
        if tool_name:
            migration = self.TOOL_MIGRATIONS.get(tool_name)
            if not migration:
                return f"No migration information for tool '{tool_name}'"

            guide = f"# Migration Guide: {tool_name}\n\n"
            guide += f"**Status**: {migration.status.value}\n"
            guide += f"**New Tool**: `{migration.new_name}`\n"

            if migration.deprecated_since:
                guide += f"**Deprecated Since**: v{migration.deprecated_since}\n"
            if migration.removal_version:
                guide += f"**Removal Version**: v{migration.removal_version}\n"

            guide += "\n## Parameter Mapping\n"
            for old, new in migration.param_mapping.items():
                if new:
                    guide += f"- `{old}` → `{new}`\n"
                else:
                    guide += f"- `{old}` → (no direct mapping, see notes)\n"

            if migration.migration_notes:
                guide += f"\n## Notes\n{migration.migration_notes}\n"

            return guide

        # General migration guide
        guide = "# Zulip MCP v2.5.0 Migration Guide\n\n"
        guide += "## Tool Consolidation\n\n"

        categories = {
            "Messaging": ["send_message", "get_messages", "edit_message", "add_reaction"],
            "Streams": ["get_streams", "create_stream", "rename_stream", "archive_stream"],
            "Agents": ["register_agent", "agent_message", "poll_agent_events"],
            "Search": ["search_messages", "get_daily_summary"],
            "Administration": ["New admin tools with permission boundaries"],
        }

        for category, tools in categories.items():
            guide += f"### {category}\n"
            for tool in tools:
                if tool in self.TOOL_MIGRATIONS:
                    migration = self.TOOL_MIGRATIONS[tool]
                    guide += f"- `{tool}` → `{migration.new_name}`\n"
            guide += "\n"

        return guide

    def complete_v25_migration(self) -> Dict[str, Any]:
        """Complete the v2.5.0 architecture consolidation.
        
        This method provides a final summary of the v2.5.0 migration
        from 24+ tools to 7 consolidated categories.
        
        Returns:
            Migration completion summary
        """
        v25_categories = {
            "messaging_v25": {
                "tools": 3,
                "description": "Message operations with identity-aware capabilities",
                "functions": ["message", "search_messages", "edit_message", "bulk_operations"]
            },
            "streams_v25": {
                "tools": 2, 
                "description": "Stream and topic management with enhanced permissions",
                "functions": ["manage_streams", "manage_topics"]
            },
            "events_v25": {
                "tools": 3,
                "description": "Real-time event streaming replacing legacy agent system", 
                "functions": ["register_events", "get_events", "listen_events"]
            },
            "users_v25": {
                "tools": 3,
                "description": "Identity management with multi-credential support",
                "functions": ["manage_users", "switch_identity", "manage_user_groups"]
            },
            "search_v25": {
                "tools": 2,
                "description": "Advanced search with analytics and performance optimization",
                "functions": ["advanced_search", "analytics"]
            },
            "files_v25": {
                "tools": 2, 
                "description": "File management with upload optimization and security",
                "functions": ["upload_file", "manage_files"]
            },
            "admin_v25": {
                "tools": 2,
                "description": "Administrative operations with clear permission boundaries",
                "functions": ["admin_operations", "customize_organization"]
            }
        }
        
        # Calculate migration statistics
        total_new_tools = sum(cat["tools"] for cat in v25_categories.values())
        total_functions = sum(len(cat["functions"]) for cat in v25_categories.values())
        migrated_legacy_tools = len(self.TOOL_MIGRATIONS)
        
        completion_summary = {
            "status": "completed",
            "version": "2.5.0",
            "architecture": "consolidated",
            "completion_date": datetime.utcnow().isoformat(),
            "migration_stats": {
                "legacy_tools_migrated": migrated_legacy_tools,
                "new_tool_categories": len(v25_categories),
                "total_new_tools": total_new_tools,
                "total_functions": total_functions,
                "consolidation_ratio": f"{migrated_legacy_tools}→{total_new_tools}",
            },
            "v25_architecture": v25_categories,
            "key_improvements": [
                "Identity-aware operations with multi-credential support",
                "Enhanced permission boundaries and security",
                "Performance optimization with intelligent caching",
                "Stateless event streaming replacing legacy agents",
                "Comprehensive error handling and logging",
                "Backward compatibility preservation during transition",
                "Admin tools with clear capability requirements"
            ],
            "deprecation_status": {
                "deprecated_tools": len([
                    m for m in self.TOOL_MIGRATIONS.values() 
                    if m.status == MigrationStatus.DEPRECATED
                ]),
                "active_tools": len([
                    m for m in self.TOOL_MIGRATIONS.values()
                    if m.status == MigrationStatus.ACTIVE
                ]),
                "removal_timeline": "3.0.0"
            }
        }
        
        logger.info("v2.5.0 architecture consolidation completed successfully")
        return completion_summary