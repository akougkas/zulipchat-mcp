"""Error path tests for streams_v25 operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_missing_source_topic_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()

    async def execute(tool, params, func, identity=None):
        class Client:
            pass

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    for op in ("move", "mute", "unmute", "mark_read", "delete"):
        mock_validator.validate_tool_params.return_value = {
            "stream_id": 1,
            "operation": op,
        }
        res = await manage_topics(stream_id=1, operation=op)
        assert res["status"] == "error"
        assert "source_topic" in res["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_missing_args_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()

    # update without ids/names
    mock_validator.validate_tool_params.return_value = {
        "operation": "update",
        "properties": {"name": "x"},
    }

    async def execute(tool, params, func, identity=None):
        return await func(Mock(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res_upd = await manage_streams(operation="update", properties={"name": "x"})
    assert res_upd["status"] == "error"

    # delete without ids/names
    mock_validator.validate_tool_params.return_value = {"operation": "delete"}
    res_del = await manage_streams(operation="delete")
    assert res_del["status"] == "error"
