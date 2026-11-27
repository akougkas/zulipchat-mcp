"""Test two-tier tool registration and merged tool dispatch."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

# --- Registration counting infrastructure ---


class ToolCountingMCP:
    """MCP mock that counts registered tools by name."""

    def __init__(self):
        self._tools: dict[str, Any] = {}

    def tool(self, name: str | None = None, description: str | None = None, **kwargs):
        def _wrap(fn):
            tool_name = name or fn.__name__
            self._tools[tool_name] = {
                "fn": fn,
                "description": description,
                "kwargs": kwargs,
            }
            return fn

        return _wrap

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def tool_names(self) -> set[str]:
        return set(self._tools.keys())


# --- Core vs Extended registration tests ---


EXTENDED_TOOL_COUNT = 53


class TestToolRegistration:
    def test_core_registers_exactly_the_core_tools(self):
        from zulipchat_mcp.tools import CORE_TOOLS, register_core_tools

        mcp = ToolCountingMCP()
        register_core_tools(mcp)
        assert mcp.tool_names == set(CORE_TOOLS)
        assert mcp.tool_count == len(CORE_TOOLS) == 13

    def test_extended_adds_tools_beyond_core(self):
        from zulipchat_mcp.tools import register_core_tools, register_extended_tools

        mcp = ToolCountingMCP()
        register_core_tools(mcp)
        register_extended_tools(mcp)
        assert mcp.tool_count == EXTENDED_TOOL_COUNT

    def test_no_duplicate_tool_names(self):
        """Core and extended should not register the same tool name."""
        from zulipchat_mcp.tools import register_core_tools, register_extended_tools

        core_mcp = ToolCountingMCP()
        register_core_tools(core_mcp)

        ext_mcp = ToolCountingMCP()
        register_extended_tools(ext_mcp)

        overlap = core_mcp.tool_names & ext_mcp.tool_names
        assert overlap == set(), f"Duplicate tools in core and extended: {overlap}"

    def test_extended_includes_raw_flag_api(self):
        from zulipchat_mcp.tools import register_extended_tools

        mcp = ToolCountingMCP()
        register_extended_tools(mcp)
        assert "update_message_flags_for_narrow" in mcp.tool_names


# --- Merged tool dispatch tests ---


def _run(coro):
    """Helper to run async functions in tests."""
    return asyncio.run(coro)


class TestManageMessageFlags:
    @pytest.fixture(autouse=True)
    def captured_client(self):
        with patch("zulipchat_mcp.tools.mark_messaging.get_client"):
            yield

    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_mark_all_messages(self, mock_update):
        from zulipchat_mcp.tools.mark_messaging import mark_all_messages

        mock_update.return_value = {"status": "success", "found_newest": True}
        result = _run(mark_all_messages(flag="read", action="add"))
        assert result["status"] == "success"
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args
        assert call_kwargs[1]["narrow"] == []
        assert call_kwargs[1]["flag"] == "read"
        assert call_kwargs[1]["op"] == "add"

    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_scope_stream(self, mock_update):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        mock_update.return_value = {"status": "success", "found_newest": True}
        result = _run(
            manage_message_flags(flag="read", action="add", scope="stream", stream_id=1)
        )
        assert result["status"] == "success"
        assert mock_update.call_args[1]["narrow"] == [
            {"operator": "channel", "operand": 1}
        ]

    def test_scope_stream_missing_id(self):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        result = _run(manage_message_flags(flag="read", action="add", scope="stream"))
        assert result["status"] == "error"
        assert "stream_id required" in result["error"]["message"]

    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_scope_topic(self, mock_update):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        mock_update.return_value = {"status": "success", "found_newest": True}
        result = _run(
            manage_message_flags(
                flag="starred",
                action="add",
                scope="topic",
                stream_id=1,
                topic_name="test",
            )
        )
        assert result["status"] == "success"

    def test_scope_topic_missing_params(self):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        result = _run(manage_message_flags(flag="read", action="add", scope="topic"))
        assert result["status"] == "error"

        result = _run(
            manage_message_flags(flag="read", action="add", scope="topic", stream_id=1)
        )
        assert result["status"] == "error"
        assert "topic_name required" in result["error"]["message"]

    @patch("zulipchat_mcp.tools.mark_messaging.update_message_flags_for_narrow")
    def test_scope_narrow_with_explicit_narrow(self, mock_update):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        mock_update.return_value = {"status": "success", "found_newest": True}
        narrow = [{"operator": "sender", "operand": "user@test.com"}]
        result = _run(
            manage_message_flags(
                flag="read", action="remove", scope="narrow", narrow=narrow
            )
        )
        assert result["status"] == "success"

    def test_scope_narrow_empty(self):
        from zulipchat_mcp.tools.mark_messaging import manage_message_flags

        result = _run(manage_message_flags(flag="read", action="add", scope="narrow"))
        assert result["status"] == "error"
        assert result["error"]["recovery"]["tool"] == "mark_all_messages"

    def test_scope_all_is_not_accepted(self):
        from fastmcp import Client, FastMCP

        from zulipchat_mcp.core.tool_contract import ToolContractMiddleware
        from zulipchat_mcp.tools import register_core_tools

        mcp = FastMCP("flags", tasks=False)
        mcp.add_middleware(ToolContractMiddleware())
        register_core_tools(mcp)

        async def call():
            async with Client(mcp) as client:
                return await client.call_tool(
                    "manage_message_flags",
                    {"flag": "read", "action": "add", "scope": "all"},
                    raise_on_error=False,
                )

        result = _run(call())
        assert result.is_error
        assert result.structured_content["error"]["code"] == "INVALID_ARGUMENT"


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
        mock_by_email.assert_called_once_with(
            "a@b.com", include_custom_profile_fields=False
        )

    def test_neither(self):
        from zulipchat_mcp.tools.users import get_user

        result = _run(get_user())
        assert result["status"] == "error"
        assert "Provide user_id or email" in result["error"]["message"]


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


class TestScheduledMessageValidation:
    def test_channel_message_needs_a_topic(self):
        from zulipchat_mcp.tools.schedule_messaging import create_scheduled_message

        with patch("zulipchat_mcp.tools.schedule_messaging.get_client"):
            result = _run(
                create_scheduled_message(
                    type="stream",
                    to=1,
                    content="hi",
                    scheduled_delivery_timestamp=9999999999,
                )
            )
        assert result["error"]["code"] == "INVALID_ARGUMENT"

    def test_update_needs_a_field(self):
        from zulipchat_mcp.tools.schedule_messaging import update_scheduled_message

        with patch("zulipchat_mcp.tools.schedule_messaging.get_client") as client:
            result = _run(update_scheduled_message(scheduled_message_id=1))
        assert result["status"] == "error"
        client.return_value.client.call_endpoint.assert_not_called()
