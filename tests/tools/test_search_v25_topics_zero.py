"""Advanced_search topics across streams with zero matching topics."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="topics-zero")
async def test_advanced_search_topics_zero_results(_mock_key, mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, *args, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "streams": [
                {"stream_id": 1, "name": "general"},
                {"stream_id": 2, "name": "dev"},
            ]}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            # Topics that don't match query 'deploy'
            return {"result": "success", "topics": [{"name": "random"}, {"name": "chatter"}]}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="deploy",
        search_type=["topics"],
        limit=10,
        use_cache=False,
    )
    assert out["status"] == "success"
    res = out["results"]["topics"]
    assert res["count"] == 0 and res["has_more"] is False and res["topics"] == []

