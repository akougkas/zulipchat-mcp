"""Daily summary: error stream continues; single active stream insights."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _m(i: int, stream: str, sender: str, topic: str):
    return {
        "id": i,
        "display_recipient": stream,
        "sender_full_name": sender,
        "subject": topic,
        "timestamp": int(datetime.now().timestamp()),
        "content": "x",
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_get_daily_summary_error_continue(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import get_daily_summary

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    msgs_ok = [_m(1, "ok", "Alice", "t1"), _m(2, "ok", "Bob", "t2")]

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            narrow = kwargs.get("narrow", [])
            operand = next(
                (d.get("operand") for d in narrow if d.get("operator") == "stream"), ""
            )
            if operand == "bad":
                return {"result": "error", "msg": "fail"}
            if operand == "empty":
                return {"result": "success", "messages": []}
            return {"result": "success", "messages": msgs_ok}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # Include one error stream, one empty, and one with data
    out = await get_daily_summary(streams=["bad", "empty", "ok"], hours_back=24)
    assert out["status"] == "success"
    # Only messages from the OK stream counted
    assert out["total_messages"] == len(msgs_ok)
    # Single active stream insights
    assert out["insights"]["active_streams_count"] == 1
    assert out["insights"]["average_messages_per_active_stream"] == len(msgs_ok)
