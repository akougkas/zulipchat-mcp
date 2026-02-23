"""Test two-tier tool registration and merged tool dispatch."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# --- Registration counting infrastructure ---

class ToolCountingMCP:
    """MCP mock that counts registered tools by name."""

    def __init__(self):
        self._tools: dict[str, Any] = {}

    def tool(self, name: str | None = None, description: str | None = None):
        def _wrap(fn):
            tool_name = name or fn.__name__
            self._tools[tool_name] = {"fn": fn, "description": description}
            return fn
        return _wrap

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def tool_names(self) -> set[str]:
        return set(self._tools.keys())


# --- Core vs Extended registration tests ---

class TestToolRegistration:
    def test_core_registers_exactly_19_tools(self):
        from zulipchat_mcp.tools import register_core_tools

        mcp = ToolCountingMCP()
        register_core_tools(mcp)
        assert mcp.tool_count == 19, (
            f"Expected 19 core tools, got {mcp.tool_count}: {sorted(mcp.tool_names)}"
        )

    def test_core_tool_names(self):
        from zulipchat_mcp.tools import register_core_tools

        mcp = ToolCountingMCP()
        register_core_tools(mcp)
        expected = {
            # Messaging (4)
            "send_message", "edit_message", "get_message", "add_reaction",
            # Search & Discovery (4)
            "search_messages", "get_streams", "get_stream_info", "get_stream_topics",
            # Users (3)
            "resolve_user", "get_users", "get_own_user",
            # Agent Communication (5)
            "teleport_chat", "register_agent", "agent_message",
            "request_user_input", "wait_for_response",
            # System & Flags (3)
            "switch_identity", "server_info", "manage_message_flags",
        }
        assert mcp.tool_names == expected

    def test_extended_adds_tools_beyond_core(self):
        from zulipchat_mcp.tools import register_core_tools, register_extended_tools

        mcp = ToolCountingMCP()
        register_core_tools(mcp)
        core_count = mcp.tool_count

        register_extended_tools(mcp)
        total = mcp.tool_count

        assert total > core_count
        # Extended adds ~38 tools on top of 19 core = ~57 total
        assert total >= 50, f"Expected ~55+ total tools, got {total}"
        assert total <= 65, f"Expected ~55-60 total tools, got {total}"

    def test_no_duplicate_tool_names(self):
        """Core and extended should not register the same tool name."""
        from zulipchat_mcp.tools import register_core_tools, register_extended_tools

        core_mcp = ToolCountingMCP()
        register_core_tools(core_mcp)

        ext_mcp = ToolCountingMCP()
        register_extended_tools(ext_mcp)

        overlap = core_mcp.tool_names & ext_mcp.tool_names
        assert overlap == set(), f"Duplicate tools in core and extended: {overlap}"

    def test_extended_includes_merged_tools(self):
        from zulipchat_mcp.tools import register_extended_tools

        mcp = ToolCountingMCP()
        register_extended_tools(mcp)

        merged_tools = {
            "get_user", "manage_user_mute", "toggle_reaction",
            "manage_task", "afk_mode", "manage_scheduled_message",
        }
        assert merged_tools.issubset(mcp.tool_names), (
            f"Missing merged tools: {merged_tools - mcp.tool_names}"
        )

    def test_extended_includes_raw_flag_api(self):
        from zulipchat_mcp.tools import register_extended_tools

        mcp = ToolCountingMCP()
        register_extended_tools(mcp)
        assert "update_message_flags_for_narrow" in mcp.tool_names


# --- Merged tool dispatch tests ---

def _run(coro):
    """Helper to run async functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestManageMessageFlags:
    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_scope_all(self, mock_update):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        mock_update.return_value = {"status": "success"}
        result = _run(manage_message_flags(flag="read", action="add", scope="all"))
        assert result["status"] == "success"
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args
        assert call_kwargs[1]["narrow"] == []
        assert call_kwargs[1]["flag"] == "read"
        assert call_kwargs[1]["op"] == "add"

    @patch("zulipchat_mcp.tools.mark_messaging._resolve_stream_name", return_value="general")
    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_scope_stream(self, mock_update, mock_resolve):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        mock_update.return_value = {"status": "success"}
        result = _run(manage_message_flags(
            flag="read", action="add", scope="stream", stream_id=1
        ))
        assert result["status"] == "success"
        mock_resolve.assert_called_once_with(1)

    def test_scope_stream_missing_id(self):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        result = _run(manage_message_flags(flag="read", action="add", scope="stream"))
        assert result["status"] == "error"
        assert "stream_id required" in result["error"]

    @patch("zulipchat_mcp.tools.mark_messaging._resolve_stream_name", return_value="general")
    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_scope_topic(self, mock_update, mock_resolve):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        mock_update.return_value = {"status": "success"}
        result = _run(manage_message_flags(
            flag="starred", action="add", scope="topic", stream_id=1, topic_name="test"
        ))
        assert result["status"] == "success"

    def test_scope_topic_missing_params(self):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        result = _run(manage_message_flags(flag="read", action="add", scope="topic"))
        assert result["status"] == "error"

        result = _run(manage_message_flags(
            flag="read", action="add", scope="topic", stream_id=1
        ))
        assert result["status"] == "error"
        assert "topic_name required" in result["error"]

    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_scope_narrow_with_explicit_narrow(self, mock_update):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        mock_update.return_value = {"status": "success"}
        narrow = [{"operator": "sender", "operand": "user@test.com"}]
        result = _run(manage_message_flags(
            flag="read", action="remove", scope="narrow", narrow=narrow
        ))
        assert result["status"] == "success"

    def test_scope_narrow_empty(self):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        result = _run(manage_message_flags(flag="read", action="add", scope="narrow"))
        assert result["status"] == "error"


class TestGetUser:
    @patch("zulipchat_mcp.tools.users.get_user_by_id")
    def test_by_id(self, mock_by_id):
        from zulipchat_mcp.tools.users import get_user

        mock_by_id.return_value = {"status": "success", "user": {"user_id": 1}}
        result = _run(get_user(user_id=1))
        assert result["status"] == "success"
        mock_by_id.assert_called_once_with(1, include_custom_profile_fields=False)

    @patch("zulipchat_mcp.tools.users.get_user_by_email")
    def test_by_email(self, mock_by_email):
        from zulipchat_mcp.tools.users import get_user

        mock_by_email.return_value = {"status": "success", "user": {"email": "a@b.com"}}
        result = _run(get_user(email="a@b.com"))
        assert result["status"] == "success"
        mock_by_email.assert_called_once_with("a@b.com", include_custom_profile_fields=False)

    def test_neither(self):
        from zulipchat_mcp.tools.users import get_user

        result = _run(get_user())
        assert result["status"] == "error"
        assert "Provide user_id or email" in result["error"]


class TestManageUserMute:
    @patch("zulipchat_mcp.tools.users.mute_user")
    def test_mute(self, mock_mute):
        from zulipchat_mcp.tools.users import manage_user_mute

        mock_mute.return_value = {"status": "success", "action": "muted"}
        result = _run(manage_user_mute(muted_user_id=42, action="mute"))
        assert result["status"] == "success"
        mock_mute.assert_called_once_with(42)

    @patch("zulipchat_mcp.tools.users.unmute_user")
    def test_unmute(self, mock_unmute):
        from zulipchat_mcp.tools.users import manage_user_mute

        mock_unmute.return_value = {"status": "success", "action": "unmuted"}
        result = _run(manage_user_mute(muted_user_id=42, action="unmute"))
        assert result["status"] == "success"
        mock_unmute.assert_called_once_with(42)


class TestToggleReaction:
    @patch("zulipchat_mcp.tools.emoji_messaging.add_reaction")
    def test_add(self, mock_add):
        from zulipchat_mcp.tools.emoji_messaging import toggle_reaction

        mock_add.return_value = {"status": "success"}
        result = _run(toggle_reaction(message_id=1, emoji_name="thumbs_up", action="add"))
        assert result["status"] == "success"
        mock_add.assert_called_once()

    @patch("zulipchat_mcp.tools.emoji_messaging.remove_reaction")
    def test_remove(self, mock_remove):
        from zulipchat_mcp.tools.emoji_messaging import toggle_reaction

        mock_remove.return_value = {"status": "success"}
        result = _run(toggle_reaction(message_id=1, emoji_name="thumbs_up", action="remove"))
        assert result["status"] == "success"
        mock_remove.assert_called_once()


class TestManageTask:
    @patch("zulipchat_mcp.tools.agents.start_task")
    def test_start(self, mock_start):
        from zulipchat_mcp.tools.agents import manage_task

        mock_start.return_value = {"status": "success", "task_id": "abc"}
        result = manage_task(action="start", agent_id="agent1", name="test task")
        assert result["status"] == "success"
        mock_start.assert_called_once_with("agent1", "test task", "")

    @patch("zulipchat_mcp.tools.agents.update_task_progress")
    def test_update(self, mock_update):
        from zulipchat_mcp.tools.agents import manage_task

        mock_update.return_value = {"status": "success"}
        result = manage_task(action="update", task_id="t1", progress=50, status="working")
        assert result["status"] == "success"
        mock_update.assert_called_once_with("t1", 50, "working")

    @patch("zulipchat_mcp.tools.agents.complete_task")
    def test_complete(self, mock_complete):
        from zulipchat_mcp.tools.agents import manage_task

        mock_complete.return_value = {"status": "success"}
        result = manage_task(action="complete", task_id="t1", outputs="done")
        assert result["status"] == "success"
        mock_complete.assert_called_once_with("t1", "done", "")

    def test_start_missing_agent_id(self):
        from zulipchat_mcp.tools.agents import manage_task

        result = manage_task(action="start")
        assert result["status"] == "error"

    def test_unknown_action(self):
        from zulipchat_mcp.tools.agents import manage_task

        result = manage_task(action="bogus")
        assert result["status"] == "error"


class TestAfkMode:
    @patch("zulipchat_mcp.tools.agents.enable_afk_mode")
    def test_enable(self, mock_enable):
        from zulipchat_mcp.tools.agents import afk_mode

        mock_enable.return_value = {"status": "success"}
        result = afk_mode(action="enable", hours=4, reason="lunch")
        assert result["status"] == "success"
        mock_enable.assert_called_once_with(4, "lunch")

    @patch("zulipchat_mcp.tools.agents.disable_afk_mode")
    def test_disable(self, mock_disable):
        from zulipchat_mcp.tools.agents import afk_mode

        mock_disable.return_value = {"status": "success"}
        result = afk_mode(action="disable")
        assert result["status"] == "success"

    @patch("zulipchat_mcp.tools.agents.get_afk_status")
    def test_status(self, mock_status):
        from zulipchat_mcp.tools.agents import afk_mode

        mock_status.return_value = {"status": "success", "afk_state": {"enabled": False}}
        result = afk_mode(action="status")
        assert result["status"] == "success"

    def test_unknown_action(self):
        from zulipchat_mcp.tools.agents import afk_mode

        result = afk_mode(action="bogus")
        assert result["status"] == "error"


class TestManageScheduledMessage:
    @patch("zulipchat_mcp.tools.schedule_messaging.create_scheduled_message")
    def test_create(self, mock_create):
        from zulipchat_mcp.tools.schedule_messaging import manage_scheduled_message

        mock_create.return_value = {"status": "success", "scheduled_message_id": 1}
        result = _run(manage_scheduled_message(
            action="create", type="stream", to=1, content="hi",
            scheduled_delivery_timestamp=9999999999, topic="test",
        ))
        assert result["status"] == "success"
        mock_create.assert_called_once()

    def test_create_missing_params(self):
        from zulipchat_mcp.tools.schedule_messaging import manage_scheduled_message

        result = _run(manage_scheduled_message(action="create"))
        assert result["status"] == "error"
        assert "required for create" in result["error"]

    @patch("zulipchat_mcp.tools.schedule_messaging.update_scheduled_message")
    def test_update(self, mock_update):
        from zulipchat_mcp.tools.schedule_messaging import manage_scheduled_message

        mock_update.return_value = {"status": "success"}
        result = _run(manage_scheduled_message(
            action="update", scheduled_message_id=1, content="updated"
        ))
        assert result["status"] == "success"

    def test_update_missing_id(self):
        from zulipchat_mcp.tools.schedule_messaging import manage_scheduled_message

        result = _run(manage_scheduled_message(action="update"))
        assert result["status"] == "error"

    @patch("zulipchat_mcp.tools.schedule_messaging.delete_scheduled_message")
    def test_delete(self, mock_delete):
        from zulipchat_mcp.tools.schedule_messaging import manage_scheduled_message

        mock_delete.return_value = {"status": "success"}
        result = _run(manage_scheduled_message(action="delete", scheduled_message_id=1))
        assert result["status"] == "success"

    def test_delete_missing_id(self):
        from zulipchat_mcp.tools.schedule_messaging import manage_scheduled_message

        result = _run(manage_scheduled_message(action="delete"))
        assert result["status"] == "error"

    def test_unknown_action(self):
        from zulipchat_mcp.tools.schedule_messaging import manage_scheduled_message

        result = _run(manage_scheduled_message(action="bogus"))
        assert result["status"] == "error"
