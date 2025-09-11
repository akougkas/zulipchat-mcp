"""Additional tests for events_v25 listen and error paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_listen_events_short_duration_no_events(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import listen_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "event_types": ["message"],
        "duration": 0,  # end immediately
        "poll_interval": 0,
        "max_events_per_poll": 10,
        "all_public_streams": False,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "queue_id": "q-listen", "last_event_id": 0}

            def get_events(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "events": []}

            def deregister(self, queue_id):  # type: ignore[no-redef]
                return {"result": "success"}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await listen_events(event_types=["message"], duration=0, poll_interval=0)
    assert res["status"] == "success"
    assert res["total_events"] == 0


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_register_events_error_path(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import register_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "event_types": ["message"],
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "error", "msg": "bad request"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res = await register_events(event_types=["message"])
    assert res["status"] == "error"
    assert "bad request" in res["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_get_events_error_queue_invalid(mock_managers) -> None:
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
                return {"result": "error", "msg": "Queue q1 is invalid"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await get_events(queue_id="q1", last_event_id=0, dont_block=True, timeout=1)
    assert res["status"] == "error"
    assert res["queue_still_valid"] is False

