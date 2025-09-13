"""Additional get_events flags coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_get_events_longpoll_with_flags(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import get_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_events(self, **kwargs):  # type: ignore[no-redef]
                assert kwargs.get("timeout") == 2
                assert kwargs.get("apply_markdown") is True
                assert kwargs.get("client_gravatar") is True
                return {"result": "success", "events": [{"id": 7}]}

        return await func(
            Client(),
            {
                "queue_id": "q1",
                "last_event_id": 5,
                "dont_block": False,
                "timeout": 2,
                "apply_markdown": True,
                "client_gravatar": True,
            },
        )

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await get_events(
        queue_id="q1",
        last_event_id=5,
        dont_block=False,
        timeout=2,
        apply_markdown=True,
        client_gravatar=True,
    )
    assert res["status"] == "success"
    assert res["last_event_id"] == 7
