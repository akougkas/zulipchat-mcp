"""Tests for streams_v25.manage_topics operations: list/mute/unmute/move."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_list_basic(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "list",
        "max_results": 5,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
                return {"result": "success", "topics": [{"name": "t1"}, {"name": "t2"}]}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res = await manage_topics(stream_id=10, operation="list", max_results=5)
    assert res["status"] == "success"
    assert res["count"] == 2


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_mute_unmute_success(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    # Mute
    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "mute",
        "source_topic": "t1",
    }

    async def execute_mute(tool, params, func, identity=None):
        class Client:
            def mute_topic(self, stream_id, topic):  # type: ignore[no-redef]
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute_mute)
    res_mute = await manage_topics(stream_id=10, operation="mute", source_topic="t1")
    assert res_mute["status"] == "success"
    assert res_mute["operation"] == "mute"

    # Unmute
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "unmute",
        "source_topic": "t1",
    }

    async def execute_unmute(tool, params, func, identity=None):
        class Client:
            def unmute_topic(self, stream_id, topic):  # type: ignore[no-redef]
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute_unmute)
    res_unmute = await manage_topics(stream_id=10, operation="unmute", source_topic="t1")
    assert res_unmute["status"] == "success"
    assert res_unmute["operation"] == "unmute"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_move_no_messages_error(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "move",
        "source_topic": "old",
        "target_topic": "new",
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_messages(self, request):  # type: ignore[no-redef]
                return {"result": "success", "messages": []}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res = await manage_topics(stream_id=10, operation="move", source_topic="old", target_topic="new")
    assert res["status"] == "error"
    assert "No messages found" in res["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_mark_read_and_delete_success(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()

    # mark_read
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "mark_read",
        "source_topic": "t1",
    }

    async def exec_mark(tool, params, func, identity=None):
        class Client:
            def mark_topic_as_read(self, stream_id, topic_name):  # type: ignore[no-redef]
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_mark)
    res_mr = await manage_topics(stream_id=10, operation="mark_read", source_topic="t1")
    assert res_mr["status"] == "success"
    assert res_mr["operation"] == "mark_read"

    # delete
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "delete",
        "source_topic": "t1",
    }

    async def exec_del(tool, params, func, identity=None):
        class Client:
            def delete_topic(self, stream_id, topic_name):  # type: ignore[no-redef]
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_del)
    res_del = await manage_topics(stream_id=10, operation="delete", source_topic="t1")
    assert res_del["status"] == "success"
    assert res_del["operation"] == "delete"
