"""Hit remaining sentiment grouping branches (day/stream)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_sentiment_group_by_day_and_stream(
    mock_managers, make_msg
) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    msgs = [
        make_msg(1, minutes_ago=1, stream="general", content="great work"),
        make_msg(2, minutes_ago=2, stream="dev", content="bad issue"),
        make_msg(3, minutes_ago=3, stream="dev", content="good news"),
    ]

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return self.get_messages(kwargs)

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # group_by day
    day = await analytics(metric="sentiment", group_by="day", format="chart_data")
    assert day["status"] == "success" and "chart_data" in day

    # group_by stream
    stream = await analytics(metric="sentiment", group_by="stream")
    assert stream["status"] == "success" and "sentiment" in stream["data"]
