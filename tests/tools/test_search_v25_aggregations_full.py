"""Full aggregations coverage for advanced_search messages branch."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _msg(id: int, sender: str, stream: str, ts: int, content: str, reactions=None):
    return {
        "id": id,
        "sender_full_name": sender,
        "display_recipient": stream,
        "timestamp": ts,
        "content": content,
        "reactions": reactions or [],
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="aggs")
async def test_advanced_search_full_aggregations(_mock_key, mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search, NarrowFilter

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    now = int(datetime.now().timestamp())
    msgs = [
        _msg(1, "Alice", "general", now - 60, "Deploy release v1", reactions=[{"emoji_name": ":tada:", "user_ids": [1,2]}]),
        _msg(2, "Bob", "dev", now - 120, "Fix bug and error"),
        _msg(3, "Alice", "general", now - 200, "Investigate logs and error", reactions=[{"emoji_name": ":bug:", "user_ids": [2]}]),
        _msg(4, "Charlie", "ops", now - 10, "Deploy script ready"),
    ]

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="deploy",
        search_type=["messages"],
        narrow=[NarrowFilter("stream", "general")],
        aggregations=["count_by_user", "count_by_stream", "count_by_time", "word_frequency", "emoji_usage"],
        sort_by="relevance",
        limit=3,
        highlight=False,
        use_cache=False,
    )
    assert out["status"] == "success"
    aggs = out["aggregations"]["messages"]
    assert set(["count_by_user", "count_by_stream", "count_by_time", "word_frequency", "emoji_usage"]).issubset(set(aggs.keys()))

