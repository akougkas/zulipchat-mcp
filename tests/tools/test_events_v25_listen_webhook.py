"""Test events_v25.listen_events with webhook and filters."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
@patch("zulipchat_mcp.tools.events_v25._send_webhook")
async def test_listen_events_with_webhook_and_filter(mock_send, mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import listen_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "event_types": ["message"],
        "duration": 0.01,
        "poll_interval": 0,
        "max_events_per_poll": 10,
        "all_public_streams": False,
        "callback_url": "http://example",
        "filters": {"type": "message"},
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "queue_id": "q1", "last_event_id": 0}

            def get_events(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "events": [{"id": 1, "type": "message"}]}

            def deregister(self, queue_id):  # type: ignore[no-redef]
                return {"result": "success"}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    mock_send.return_value = AsyncMock()

    res = await listen_events(
        event_types=["message"],
        duration=0.01,
        poll_interval=0,
        callback_url="http://example",
        filters={"type": "message"},
    )
    assert res["status"] == "success"
    assert res["total_events"] >= 1


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_listen_events_filter_mismatch_no_webhook(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import listen_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "event_types": ["message"],
        "duration": 0.01,
        "poll_interval": 0,
        "max_events_per_poll": 10,
        "filters": {"type": "typing"},
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "queue_id": "q2", "last_event_id": 0}

            def get_events(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "events": [{"id": 1, "type": "message"}]}

            def deregister(self, queue_id):  # type: ignore[no-redef]
                return {"result": "success"}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res = await listen_events(
        event_types=["message"],
        duration=0.01,
        poll_interval=0,
        filters={"type": "typing"},
    )
    assert res["status"] == "success"
    assert res["total_events"] == 0
