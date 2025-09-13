"""Search v2.5 error and cache path tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
async def test_advanced_search_empty_query_error() -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    res = await advanced_search(query=" ")
    assert res["status"] == "error"
    assert "Query cannot be empty" in res["error"]


@pytest.mark.asyncio
async def test_advanced_search_invalid_limit_error() -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    res = await advanced_search(query="q", limit=0)
    assert res["status"] == "error"
    assert "Limit must be between" in res["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_advanced_search_cache_hit(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import NarrowFilter, advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": []}

        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages(
                {
                    "anchor": anchor,
                    "num_before": num_before,
                    "num_after": num_after,
                    "narrow": narrow or [],
                }
            )

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    nf = NarrowFilter("stream", "general")

    # First call populates cache
    res1 = await advanced_search(
        query="hello", search_type=["messages"], narrow=[nf], use_cache=True
    )
    assert res1["status"] == "success"
    assert res1["metadata"]["from_cache"] is False

    # Second call returns from cache
    res2 = await advanced_search(
        query="hello", search_type=["messages"], narrow=[nf], use_cache=True
    )
    assert res2["status"] == "success"
    # Cache hit marks top-level flag per implementation
    assert res2.get("from_cache", False) is True
