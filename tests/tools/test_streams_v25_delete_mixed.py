"""Delete mixed-success/error/exception for manage_streams.delete."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_delete_mixed(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def delete_stream(self, stream_id):  # type: ignore[no-redef]
            if stream_id == 1:
                return {"result": "success"}
            if stream_id == 2:
                return {"result": "error", "msg": "denied"}
            raise RuntimeError("boom")

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams("delete", stream_ids=[1, 2, 3])
    assert res["status"] == "success" and res["operation"] == "delete"
    assert len(res["results"]) == 3
