"""Tests for search_v25.get_daily_summary to cover stream summaries and insights."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_get_daily_summary_two_streams(mock_managers, make_msg, fake_client_class) -> None:
    from zulipchat_mcp.tools.search_v25 import get_daily_summary

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    now = int(datetime.now().timestamp())
    msgs_a = [
        make_msg(1, minutes_ago=2, stream="general", subject="t1", sender="Alice", content="project meeting"),
        make_msg(2, minutes_ago=1, stream="general", subject="t1", sender="Bob", content="bug fix"),
    ]
    msgs_b = [
        make_msg(3, minutes_ago=1, stream="dev", subject="deploy", sender="Alice", content="release deploy"),
    ]

    class Client(fake_client_class):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            narrow = kwargs.get("narrow", [])
            if any(d.get("operand") == "general" for d in narrow):
                return {"result": "success", "messages": msgs_a}
            return {"result": "success", "messages": msgs_b}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await get_daily_summary(streams=["general", "dev"], hours_back=24)
    assert out["status"] == "success"
    assert out["total_messages"] == 3
    assert out["streams"]["general"]["message_count"] == 2
    assert out["streams"]["dev"]["active_user_count"] == 1
    assert out["insights"]["active_streams_count"] >= 1
