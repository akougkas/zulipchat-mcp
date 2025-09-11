"""Additional minimal tests for streams v2.5.0 tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_create_missing_names(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {"operation": "create"}

    async def execute(tool, params, func, identity=None):
        class Client:
            pass
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams(operation="create")
    assert res["status"] == "error"
    assert "stream_names required" in res["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_update_missing_props(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "update",
        "stream_ids": [1],
    }

    async def execute(tool, params, func, identity=None):
        return await func(Mock(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams(operation="update", stream_ids=[1])
    assert res["status"] == "error"
    assert "properties required" in res["error"]
