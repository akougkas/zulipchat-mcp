"""Heavy daily summary to exercise insights and top_senders slice."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_get_daily_summary_heavy_insights(
    mock_managers, make_msg, fake_client_class
) -> None:
    from zulipchat_mcp.tools.search_v25 import get_daily_summary

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    # Build many messages with >10 unique senders across 3 streams
    senders = [f"S{i}" for i in range(1, 15)]
    msgs_a = [
        make_msg(i, stream="a", sender=senders[i % len(senders)], subject=f"t{i%3}")
        for i in range(1, 20)
    ]
    msgs_b = [
        make_msg(
            100 + i,
            stream="b",
            sender=senders[(i + 1) % len(senders)],
            subject=f"u{i%2}",
        )
        for i in range(1, 12)
    ]
    msgs_c = [
        make_msg(
            200 + i,
            stream="c",
            sender=senders[(i + 2) % len(senders)],
            subject=f"v{i%4}",
        )
        for i in range(1, 9)
    ]

    class Client(fake_client_class):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            narrow = kwargs.get("narrow", [])
            operand = next(
                (d.get("operand") for d in narrow if d.get("operator") == "stream"), ""
            )
            if operand == "a":
                return {"result": "success", "messages": msgs_a}
            if operand == "b":
                return {"result": "success", "messages": msgs_b}
            return {"result": "success", "messages": msgs_c}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await get_daily_summary(streams=["a", "b", "c"], hours_back=24)
    assert out["status"] == "success" and out["total_messages"] >= 30
    assert out["insights"]["active_streams_count"] >= 2
    assert out["insights"]["total_unique_senders"] <= 10  # sliced top_senders
