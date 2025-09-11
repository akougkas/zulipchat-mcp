"""Additional minimal tests for events v2.5.0 tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_get_events_basic(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import get_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "queue_id": "q1",
        "last_event_id": 0,
        "dont_block": True,
        "timeout": 1,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_events(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "events": []}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await get_events(queue_id="q1", last_event_id=0, dont_block=True, timeout=1)
    assert res["status"] == "success"
    assert res["queue_id"] == "q1"
    assert res["event_count"] == 0

