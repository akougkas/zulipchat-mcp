"""Tests for MigrationManager covering mappings and special cases."""

from __future__ import annotations

import warnings

from zulipchat_mcp.core.migration import MigrationManager, MigrationStatus


def test_migrate_tool_call_basic_and_removed() -> None:
    mm = MigrationManager()
    # Unmapped tool returns as-is
    name, params = mm.migrate_tool_call("unknown_tool", {"a": 1})
    assert (name, params) == ("unknown_tool", {"a": 1})

    # Removed tool raises
    # Set a mapping temporarily to REMOVED to simulate
    mm.TOOL_MIGRATIONS["to_be_removed"] = mm.TOOL_MIGRATIONS["get_streams"].__class__(
        old_name="to_be_removed",
        new_name="x",
        new_params={},
        param_mapping={},
        status=MigrationStatus.REMOVED,
    )
    try:
        try:
            mm.migrate_tool_call("to_be_removed", {})
            raise AssertionError("Expected ValueError")
        except ValueError:
            pass
    finally:
        del mm.TOOL_MIGRATIONS["to_be_removed"]


def test_migrate_tool_call_with_deprecation_warning() -> None:
    mm = MigrationManager()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        name, params = mm.migrate_tool_call("get_streams", {})
        assert name == "streams.manage_streams"
        assert any(item.category is DeprecationWarning for item in w)


def test_special_migrations_get_messages_and_create_stream() -> None:
    mm = MigrationManager()
    # get_messages adds narrow
    name, params = mm.migrate_tool_call(
        "get_messages", {"stream_name": "general", "hours_back": 1}
    )
    assert name == "messaging.search_messages"
    assert any(f["operator"] == "stream" for f in params["narrow"])

    # create_stream wraps stream_name into list
    name2, params2 = mm.migrate_tool_call("create_stream", {"stream_name": "dev"})
    assert name2 == "streams.manage_streams"
    assert params2["stream_names"] == ["dev"]


def test_get_migration_status_and_guides() -> None:
    mm = MigrationManager()
    status = mm.get_migration_status()
    assert "deprecated_tools" in status and isinstance(status["migration_stats"], dict)
    guide_general = mm.get_migration_guide()
    assert "Migration Guide" in guide_general
    guide_tool = mm.get_migration_guide("get_streams")
    assert "get_streams" in guide_tool and "streams.manage_streams" in guide_tool


def test_complete_v25_migration_summary() -> None:
    mm = MigrationManager()
    summary = mm.complete_v25_migration()
    assert summary["status"] == "completed"
    assert summary["version"] == "2.5.0"
    assert "migration_stats" in summary
