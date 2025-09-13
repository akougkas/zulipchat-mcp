"""Minimal tests for events_v25 tools (v2.5.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_register_events_basic(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import register_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "event_types": ["message"],
        "all_public_streams": False,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):
                return {"result": "success", "queue_id": "q1", "last_event_id": 0}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await register_events(event_types=["message"], all_public_streams=False)
    assert res["status"] == "success"
    assert res["queue_id"] == "q1"
