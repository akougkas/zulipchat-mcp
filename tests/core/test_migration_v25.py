"""Minimal tests for MigrationManager aligned with v2.5.0 implementation."""

from zulipchat_mcp.core.migration import MigrationManager


class TestMigrationManager:
    def test_migrate_send_message(self) -> None:
        mm = MigrationManager()
        new_tool, params = mm.migrate_tool_call(
            "send_message",
            {"message_type": "stream", "stream": "general", "subject": "hello"},
        )
        assert new_tool == "messaging.message"
        # parameter mapping is shallow; original keys preserved when unmapped
        assert params["operation"] == "send"
        assert params["type"] == "stream"
        assert params["to"] == "general"
        assert params["topic"] == "hello"

    def test_migrate_get_streams(self) -> None:
        mm = MigrationManager()
        new_tool, params = mm.migrate_tool_call("get_streams", {"include_public": True})
        assert new_tool == "streams.manage_streams"
        assert params["operation"] == "list"
        assert params["include_public"] is True
