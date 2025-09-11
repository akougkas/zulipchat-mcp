"""Further coverage for events_v25: active queues and long-poll path."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_register_events_tracks_active_queues(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import register_events, get_active_queues

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "event_types": ["message"],
        "queue_lifespan_secs": 60,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "queue_id": "qtrack", "last_event_id": 1}
            def deregister(self, queue_id):  # type: ignore[no-redef]
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await register_events(event_types=["message"], queue_lifespan_secs=60)
    assert res["status"] == "success"
    active = get_active_queues()
    assert "qtrack" in active


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_get_events_success_longpoll_path(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import get_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "queue_id": "q1",
        "last_event_id": 5,
        "dont_block": False,
        "timeout": 2,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_events(self, **kwargs):  # type: ignore[no-redef]
                # Assert timeout path used
                assert kwargs.get("timeout") == 2
                return {"result": "success", "events": [{"id": 6, "type": "message"}]}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await get_events(queue_id="q1", last_event_id=5, dont_block=False, timeout=2)
    assert res["status"] == "success"
    assert res["event_count"] == 1
    assert res["last_event_id"] == 6

