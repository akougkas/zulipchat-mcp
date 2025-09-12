"""Contract tests for search_v25.analytics output shape."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from jsonschema import validate


ANALYTICS_SCHEMA = {
    "type": "object",
    "required": ["status", "metric", "time_range", "data"],
    "properties": {
        "status": {"enum": ["success"]},
        "metric": {"enum": ["activity", "sentiment", "topics", "participation"]},
        "time_range": {
            "type": "object",
            "required": ["days", "hours"],
            "properties": {
                "days": {"type": ["number", "null"]},
                "hours": {"type": ["number", "null"]},
            },
            "additionalProperties": True,
        },
        "group_by": {"type": ["string", "null"]},
        "format": {"type": "string"},
        "data": {"type": "object"},
        "metadata": {"type": "object"},
        "chart_data": {"type": ["object", "null"]},
        "detailed_insights": {"type": ["array", "null"]},
    },
    "additionalProperties": True,
}


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_contract_activity_chart(mock_managers, make_msg, fake_client_class) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    msgs = [make_msg(1), make_msg(2), make_msg(3)]

    class Client(fake_client_class):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def exec_(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_)

    out = await analytics(metric="activity", group_by="hour", format="chart_data")
    validate(out, ANALYTICS_SCHEMA)
