"""Boundary test: topics has_more when results == limit should be True."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="topics-eq")
async def test_topics_has_more_equal_limit(
    _key, mock_managers, fake_client_class
) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    limit = 4

    class Client(fake_client_class):
        def get_streams(self, *a, **k):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "s", "stream_id": 1}]}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {
                "result": "success",
                "topics": [{"name": f"topic{i}"} for i in range(1, limit + 1)],
            }

    async def exec_(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_)

    out = await advanced_search(
        query="topic", search_type=["topics"], limit=limit, use_cache=False
    )
    res = out["results"]["topics"]
    assert res["count"] == limit and res["has_more"] is True
