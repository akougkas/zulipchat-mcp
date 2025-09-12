"""Contract tests for search_v25.get_daily_summary output shape."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from jsonschema import validate


DAILY_SUMMARY_SCHEMA = {
    "type": "object",
    "required": ["status", "total_messages", "streams", "top_senders"],
    "properties": {
        "status": {"enum": ["success"]},
        "total_messages": {"type": "number"},
        "streams": {"type": "object"},
        "top_senders": {"type": "object"},
        "insights": {
            "type": ["object", "null"],
            "properties": {
                "most_active_stream": {"type": ["string", "null"]},
                "active_streams_count": {"type": "number"},
                "average_messages_per_active_stream": {"type": "number"},
                "total_unique_senders": {"type": "number"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_daily_summary_contract(mock_managers, make_msg, fake_client_class) -> None:
    from zulipchat_mcp.tools.search_v25 import get_daily_summary

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    msgs_a = [make_msg(1, stream="a", sender="A", subject="t"), make_msg(2, stream="a", sender="B", subject="t")]
    msgs_b = [make_msg(3, stream="b", sender="C", subject="u")]

    class Client(fake_client_class):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            operand = next((d.get("operand") for d in kwargs.get("narrow", []) if d.get("operator") == "stream"), "")
            return {"result": "success", "messages": msgs_a if operand == "a" else msgs_b}

    async def exec_(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_)

    out = await get_daily_summary(streams=["a", "b"], hours_back=24)
    validate(out, DAILY_SUMMARY_SCHEMA)
    # soft contract checks on top_senders and streams map
    assert isinstance(out["top_senders"], dict) and len(out["top_senders"]) <= 10
    assert set(out["streams"].keys()) == {"a", "b"}

