"""Expanded tests for messaging_v25 to raise coverage.

Covers send, draft, schedule (stub), bulk ops, and cross-posting.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_message_send_stream_success_and_missing_topic_error(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import message

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def send_message(self, mtype, recipients, content, topic):  # type: ignore[no-redef]
            return {"result": "success", "id": 1}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await message("send", "stream", ["general"], "Hi", topic="t")
    assert ok["status"] == "success"
    assert ok["operation"] == "send"

    # Missing topic error
    err = await message("send", "stream", ["general"], "Hi")
    assert err["status"] == "error"
    assert "Topic is required" in err["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_message_draft_success(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import message

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        pass

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await message("draft", "private", "user@example.com", "Draft content")
    assert res["status"] == "success"
    assert res["operation"] == "draft"
    assert res["draft_data"]["content"] == "Draft content"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
@patch("zulipchat_mcp.tools.messaging_v25.MessageScheduler")
async def test_message_schedule_with_stub_scheduler(MockScheduler, mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import message

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        config_manager = Mock()
        use_bot_identity = True
    # Stub config manager used by _execute_message
    client_cfg = {"email": "e", "api_key": "k", "site": "s"}
    Client.config_manager.get_zulip_client_config.return_value = client_cfg

    class StubSchedulerCtx:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def schedule_message(self, msg):  # type: ignore[no-redef]
            return {"result": "success", "scheduled_message_id": 99}

    MockScheduler.return_value = StubSchedulerCtx()

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ts = datetime.now() + timedelta(minutes=1)
    ok = await message("schedule", "stream", ["general"], "Hi", topic="t", schedule_at=ts)
    assert ok["status"] == "success"
    assert ok["operation"] == "schedule"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_bulk_operations_read_with_narrow_and_add_flag_error(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import bulk_operations

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": [{"id": 1}, {"id": 2}]}
        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages({"anchor": anchor, "num_before": num_before, "num_after": num_after, "narrow": narrow or []})
        def update_message_flags(self, messages, op, flag):  # type: ignore[no-redef]
            assert messages == [1, 2]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await bulk_operations(
        operation="mark_read",
        narrow=[{"operator": "stream", "operand": "general"}],
    )
    assert ok["status"] == "success"
    assert ok["affected_count"] == 2

    # add_flag without flag -> error
    err = await bulk_operations(operation="add_flag", message_ids=[1, 2])
    assert err["status"] == "error"
    assert "Flag parameter" in err["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_cross_post_message_success(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import cross_post_message

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_message(self, message_id):  # type: ignore[no-redef]
            return {
                "result": "success",
                "message": {
                    "content": "Hello",
                    "subject": "t",
                    "display_recipient": "general",
                },
            }
        def send_message(self, mtype, recipients, content, topic):  # type: ignore[no-redef]
            assert mtype == "stream"
            assert isinstance(recipients, (str, list))
            return {"result": "success", "id": 11}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await cross_post_message(123, ["dev"], target_topic="t2", add_reference=True)
    assert ok["status"] == "success"
    assert ok["total_successful"] == 1
