"""Validate TimeRange → narrow filter building for after/before bounds."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="tr")
async def test_time_range_builds_search_filters(_key, mock_managers, fake_client_class) -> None:
    from zulipchat_mcp.tools.search_v25 import TimeRange, advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    captured_narrow: list[dict] | None = None

    class Client(fake_client_class):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            nonlocal captured_narrow
            captured_narrow = kwargs.get("narrow", [])
            return {"result": "success", "messages": []}

    async def exec_(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_)

    start = datetime.now() - timedelta(days=2)
    end = datetime.now() - timedelta(days=1)
    tr = TimeRange(start=start, end=end)
    await advanced_search(query="x", search_type=["messages"], time_range=tr, use_cache=False)

    assert captured_narrow is not None
    operands = [d.get("operand", "") for d in captured_narrow]
    # Expect both after: and before: search operands present
    assert any(isinstance(o, str) and o.startswith("after:") for o in operands)
    assert any(isinstance(o, str) and o.startswith("before:") for o in operands)
