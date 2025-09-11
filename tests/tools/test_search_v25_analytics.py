"""Tests for search_v25.analytics covering activity paths and formatting."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _msg(ts_offset: int, sender="Alice", stream="general", content="Hello", subject="topic"):
    return {
        "id": 1,
        "sender_full_name": sender,
        "display_recipient": stream,
        "timestamp": int(datetime.now().timestamp()) - ts_offset,
        "content": content,
        "subject": subject,
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_activity_chart_data(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": [
                _msg(10, sender="Alice", stream="general"),
                _msg(20, sender="Bob", stream="dev"),
                _msg(30, sender="Alice", stream="general"),
            ]}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await analytics(metric="activity", group_by="hour", format="chart_data", include_stats=True)
    assert res["status"] == "success"
    assert "activity" in res["data"]
    assert "statistics" in res["data"]
    assert "chart_data" in res
    assert isinstance(res["chart_data"]["series"], list)

