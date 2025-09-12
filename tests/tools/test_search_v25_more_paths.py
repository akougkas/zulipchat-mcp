"""Extra coverage for search_v25.advanced_search paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="k")
async def test_advanced_search_oldest_and_highlights(_mock_key, mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search, NarrowFilter, TimeRange

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            msgs = [
                {"id": 1, "content": "hello docker", "sender_full_name": "Alice", "display_recipient": "dev", "subject": "t"},
                {"id": 2, "content": "docker release", "sender_full_name": "Bob", "display_recipient": "dev", "subject": "t"},
            ]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # TimeRange is unhashable in the cache key path; disable cache for this case
    res = await advanced_search(
        query="docker",
        search_type=["messages"],
        narrow=[NarrowFilter("stream", "dev")],
        time_range=TimeRange(hours=2),
        sort_by="oldest",
        limit=10,
        highlight=True,
        use_cache=False,
    )
    assert res["status"] == "success"
    msgs = res["results"]["messages"]["messages"]
    assert any(m.get("highlights") for m in msgs)
