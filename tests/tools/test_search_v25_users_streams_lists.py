"""Cover users and streams list branches in advanced_search."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="us")
async def test_advanced_search_users_streams(_mock_key, mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_users(self, *args, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "members": [{"full_name": "Alice", "email": "a@x"}]}
        def get_streams(self, *args, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "general", "description": "d", "stream_id": 1}]}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="a",
        search_type=["users", "streams"],
        use_cache=False,
    )
    assert out["status"] == "success"
    assert out["results"]["users"]["count"] == 1
    assert out["results"]["streams"]["count"] == 1

