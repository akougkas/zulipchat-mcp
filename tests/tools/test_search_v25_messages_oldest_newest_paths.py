"""Cover oldest/newest sort paths for advanced_search messages."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="ord")
async def test_advanced_search_messages_oldest_and_newest(_mock_key, mock_managers, make_msg, fake_client_class) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    # Build messages using shared factory
    messages = [
        make_msg(1, minutes_ago=50, content="x", sender="S", stream="g"),
        make_msg(2, minutes_ago=10, content="x", sender="S", stream="g"),
        make_msg(3, minutes_ago=5, content="x", sender="S", stream="g"),
    ]

    class Client(fake_client_class):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": messages}

    async def exec(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec)

    # oldest
    oldest = await advanced_search(query="x", search_type=["messages"], sort_by="oldest", limit=2, use_cache=False)
    assert oldest["status"] == "success" and oldest["results"]["messages"]["count"] == 3

    # newest
    newest = await advanced_search(query="x", search_type=["messages"], sort_by="newest", limit=2, use_cache=False)
    assert newest["status"] == "success" and newest["results"]["messages"]["count"] == 3
