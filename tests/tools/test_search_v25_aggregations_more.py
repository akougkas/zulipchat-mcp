"""More coverage for advanced_search aggregations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


def _msg(sender="Alice", stream="general", content="Hi", subject="t1"):
    return {
        "id": 1,
        "sender_full_name": sender,
        "display_recipient": stream,
        "timestamp": 1,
        "content": content,
        "subject": subject,
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="k")
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_advanced_search_aggregations_counts(mock_managers, _mock_key) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search, NarrowFilter

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {
                "result": "success",
                "messages": [
                    _msg("Alice", "general", "content one"),
                    _msg("Bob", "dev", "content two"),
                    _msg("Alice", "general", "content three"),
                ],
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    nf = NarrowFilter("stream", "general")
    res = await advanced_search(
        query="content",
        search_type=["messages"],
        narrow=[nf],
        aggregations=["count_by_user", "count_by_stream"],
        sort_by="relevance",
        limit=10,
        use_cache=False,
    )
    assert res["status"] == "success"
    aggs = res["aggregations"]["messages"]
    assert "count_by_user" in aggs
    assert "count_by_stream" in aggs
