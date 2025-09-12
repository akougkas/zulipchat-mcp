"""Advanced_search messages path: relevance + TimeRange + highlight + aggregations

Covers has_more False when results < limit, and ensures metadata.limit/sort_by
are propagated. Also touches count_by_time and emoji_usage aggregations.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from zulipchat_mcp.tools.search_v25 import TimeRange, advanced_search

 


def _msg(i: int, minutes_ago: int, content: str = "deploy", reactions=None):
    return {
        "id": i,
        "sender_full_name": "User",
        "display_recipient": "general",
        "timestamp": int((datetime.now() - timedelta(minutes=minutes_ago)).timestamp()),
        "content": content,
        "reactions": reactions or [],
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="rel-less")
async def test_advanced_search_messages_relevance_has_less(_mock_key, mock_managers) -> None:
    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    now_msgs = [
        _msg(1, 1, reactions=[{"emoji_name": ":tada:", "user_ids": [1]}]),
        _msg(2, 2),
        _msg(3, 3, reactions=[{"emoji_name": ":thumbsup:", "user_ids": [1, 2]}]),
    ]  # only 3 messages

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": now_msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="deploy",
        search_type=["messages"],
        time_range=TimeRange(hours=1),  # ensure time filters applied
        sort_by="relevance",
        limit=5,  # odd limit greater than result count
        highlight=True,
        aggregations=["count_by_time", "emoji_usage"],
        use_cache=False,
    )

    assert out["status"] == "success"
    meta = out["metadata"]
    assert meta["limit"] == 5 and meta["sort_by"] == "relevance"

    res = out["results"]["messages"]
    assert res["count"] == 3 and res["has_more"] is False
    # highlight added
    assert all("highlights" in m for m in res["messages"]) and any(
        h for m in res["messages"] for h in m["highlights"]
    )
    # aggregations present
    aggs = out["aggregations"]["messages"]
    assert "count_by_time" in aggs and "emoji_usage" in aggs
