"""Cover multi-property update loop in manage_streams.update."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_update_multiple_properties(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    calls = []

    class Client:
        def update_stream(self, stream_id, **kwargs):  # type: ignore[no-redef]
            calls.append((stream_id, kwargs))
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await manage_streams("update", stream_ids=[1, 2], properties={"is_web_public": True, "stream_post_policy": 1})
    assert out["status"] == "success" and out["operation"] == "update"
    # Ensure loop executed twice per stream (two properties)
    assert len(calls) == 4

