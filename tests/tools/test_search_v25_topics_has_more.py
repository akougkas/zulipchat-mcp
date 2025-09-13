"""Cover advanced_search topics path with has_more True."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="topics_more")
async def test_advanced_search_topics_has_more(_mock_key, mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, *args, **kwargs):  # type: ignore[no-redef]
            return {
                "result": "success",
                "streams": [{"stream_id": i, "name": f"s{i}"} for i in range(1, 4)],
            }

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            # Return many topics across streams
            return {
                "result": "success",
                "topics": [{"name": f"deploy{i}"} for i in range(1, 8)],
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="deploy",
        search_type=["topics"],
        limit=5,
        use_cache=False,
    )
    assert out["status"] == "success"
    assert out["results"]["topics"]["has_more"] is True
