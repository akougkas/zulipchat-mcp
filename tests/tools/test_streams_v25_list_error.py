"""List error branch for streams_v25.manage_streams."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_list_error(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, force_fresh=False):  # type: ignore[no-redef]
            return {"result": "error", "msg": "fail"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams("list")
    assert res["status"] == "error" and res["operation"] == "list"
