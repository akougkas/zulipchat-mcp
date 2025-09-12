"""Multi-type search coverage for search_v25.advanced_search."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="multi")
async def test_advanced_search_multi_types(_mock_key, mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": [
                {"id": 1, "content": "deploy to prod", "sender_full_name": "Alice", "display_recipient": "general", "subject": "t"},
                {"id": 2, "content": "fix error before deploy", "sender_full_name": "Bob", "display_recipient": "dev", "subject": "bugs"},
            ]}
        def get_users(self, *args, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "members": [{"full_name": "Alice", "email": "a@x"}, {"full_name": "Bob", "email": "b@x"}]}
        def get_streams(self, *args, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "streams": [
                {"name": "general", "description": "general chat", "stream_id": 1},
                {"name": "dev", "description": "dev chat", "stream_id": 2},
            ]}
        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "topics": [{"name": "deploy"}, {"name": "random"}]}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="deploy",
        search_type=["messages", "users", "streams", "topics"],
        highlight=False,
        sort_by="relevance",
        limit=10,
        use_cache=False,
    )
    assert out["status"] == "success"
    assert "messages" in out["results"] and "users" in out["results"] and "streams" in out["results"] and "topics" in out["results"]
    assert out["results"]["topics"]["count"] >= 1

