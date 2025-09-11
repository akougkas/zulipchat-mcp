"""Aggregation and caching tests for search_v25. """

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _mk_message(id: int, sender: str, stream: str, timestamp: int, content: str, reactions=None):
    return {
        "id": id,
        "sender_full_name": sender,
        "display_recipient": stream,
        "timestamp": timestamp,
        "content": content,
        "reactions": reactions or [],
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_advanced_search_aggregations_and_cache(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    now = int(datetime.now().timestamp())
    messages = [
        _mk_message(1, "Alice", "general", now - 60, "Deployment success 🎉", reactions=[{"emoji_name": ":tada:", "user_ids": [1,2]}]),
        _mk_message(2, "Bob", "dev", now - 120, "Fix bug in pipeline", reactions=[]),
        _mk_message(3, "Alice", "general", now - 200, "Investigate error logs", reactions=[{"emoji_name": ":bug:", "user_ids": [2]}]),
    ]

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": messages}
        def get_users(self, request):  # type: ignore[no-redef]
            return {"result": "success", "members": [{"full_name": "Alice", "email": "alice@example.com"}]}
        def get_streams(self, request):  # type: ignore[no-redef]
            return {"result": "success", "streams": [
                {"name": "general", "description": "All", "stream_id": 10},
                {"name": "dev", "description": "Dev", "stream_id": 11},
            ]}
        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "topics": [{"name": "deployments"}, {"name": "bugs"}]}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    aggregations = ("count_by_user", "count_by_stream", "count_by_time", "word_frequency", "emoji_usage")
    # Exercise aggregations with cache disabled to avoid hashing list in cache key
    res = await advanced_search(
        query="deployment error",
        search_type=["messages", "users", "streams", "topics"],
        aggregations=aggregations,
        highlight=True,
        sort_by="newest",
        limit=50,
        use_cache=False,
    )

    assert res["status"] == "success"
    assert "messages" in res["results"]
    assert "aggregations" in res
    assert set(res["aggregations"]["messages"].keys()) >= set(aggregations)

    # Separate caching check with parameters that are cache-key friendly
    res_cache_1 = await advanced_search(
        query="deploy cache",
        search_type=["messages"],
        highlight=False,
        sort_by="newest",
        limit=10,
        use_cache=True,
    )
    assert res_cache_1["status"] == "success"
    res_cache_2 = await advanced_search(
        query="deploy cache",
        search_type=["messages"],
        highlight=False,
        sort_by="newest",
        limit=10,
        use_cache=True,
    )
    assert res_cache_2["status"] == "success"
    assert res_cache_2.get("from_cache") is True
