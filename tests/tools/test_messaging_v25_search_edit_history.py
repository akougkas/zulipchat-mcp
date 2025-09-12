"""More messaging_v25 tests: search_messages, edit_message, message_history."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _msg(i: int = 1):
    return {
        "id": i,
        "sender_full_name": "Alice",
        "sender_email": "a@example.com",
        "timestamp": int(datetime.now().timestamp()),
        "content": "Hello world",
        "type": "stream",
        "display_recipient": "general",
        "subject": "t",
        "reactions": [],
        "flags": [],
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_search_messages_basic_success(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import search_messages

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": [_msg(1), _msg(2)]}
        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages({"anchor": anchor, "num_before": num_before, "num_after": num_after, "narrow": narrow or []})

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await search_messages(narrow=[{"operator": "stream", "operand": "general"}], num_before=2, num_after=0)
    assert res["status"] == "success"
    assert res["count"] == 2


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_edit_message_updates(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import edit_message

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def edit_message(self, message_id, content, topic, propagate_mode, send_notification_to_old_thread, send_notification_to_new_thread, stream_id):  # type: ignore[no-redef]
            assert message_id == 10
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await edit_message(10, content="New", topic="nt")
    assert res["status"] == "success"
    assert "content" in res["changes"] and "topic" in res["changes"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_message_history_success(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import message_history

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_message(self, message_id):  # type: ignore[no-redef]
            return {
                "result": "success",
                "message": {
                    "timestamp": int(datetime.now().timestamp()),
                    "sender_full_name": "Alice",
                    "sender_email": "a@example.com",
                    "content": "Changed",
                    "stream_id": 1,
                    "subject": "t",
                    "last_edit_timestamp": int(datetime.now().timestamp()),
                    "reactions": [{"emoji_name": "thumbs_up", "user_id": [1]}],
                },
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await message_history(5, include_reaction_history=True)
    assert res["status"] == "success"
    assert res["message_id"] == 5
    assert "edit_history" in res and "content_history" in res and "reaction_history" in res
