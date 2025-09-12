"""Cover relevance sort with time_range and has_more metadata in advanced_search."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _mkmsg(i: int, minutes_ago: int, content: str = "docker deploy", sender: str = "U", stream: str = "dev"):
    return {
        "id": i,
        "sender_full_name": sender,
        "display_recipient": stream,
        "timestamp": int((datetime.now() - timedelta(minutes=minutes_ago)).timestamp()),
        "content": content,
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="rel")
async def test_advanced_search_relevance_with_time_range(_mock_key, mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search, TimeRange

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    messages = [_mkmsg(i, i) for i in range(1, 12)]  # 11 messages

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": messages}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="docker",
        search_type=["messages"],
        time_range=TimeRange(hours=3),
        sort_by="relevance",
        limit=5,
        highlight=False,
        use_cache=False,
    )
    assert out["status"] == "success"
    res = out["results"]["messages"]
    assert res["count"] >= 5 and res["has_more"] is True
    assert out["metadata"]["limit"] == 5 and out["metadata"]["sort_by"] == "relevance"

