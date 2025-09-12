"""Activity analytics coverage with chart_data formatting."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _msg(ts_offset: int, stream: str, sender: str):
    return {
        "id": ts_offset,
        "display_recipient": stream,
        "sender_full_name": sender,
        "subject": "t",
        "content": "hi",
        "timestamp": int((datetime.now() - timedelta(minutes=ts_offset)).timestamp()),
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_activity_chart_hour_group(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    msgs = [_msg(5, "general", "Alice"), _msg(65, "dev", "Bob"), _msg(125, "general", "Alice")]

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await analytics(metric="activity", group_by="hour", format="chart_data", include_stats=True)
    assert out["status"] == "success" and "chart_data" in out and "statistics" in out["data"]

