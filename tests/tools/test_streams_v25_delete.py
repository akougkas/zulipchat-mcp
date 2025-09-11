"""Extra coverage for streams_v25 delete operation."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_delete_success(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "delete",
        "stream_ids": [1, 2],
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def delete_stream(self, stream_id):  # type: ignore[no-redef]
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams(operation="delete", stream_ids=[1, 2])
    assert res["status"] == "success"
    assert res["operation"] == "delete"
    assert len(res["results"]) == 2

