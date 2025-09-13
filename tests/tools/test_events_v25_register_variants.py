"""Register events variants to cover optional flags."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_register_events_all_public_and_presence(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import register_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):  # type: ignore[no-redef]
                assert kwargs.get("all_public_streams") is True
                assert kwargs.get("slim_presence") is True
                assert kwargs.get("include_subscribers") is True
                return {"result": "success", "queue_id": "qa", "last_event_id": 0}

        return await func(
            Client(),
            {
                "event_types": ["stream"],
                "all_public_streams": True,
                "slim_presence": True,
                "include_subscribers": True,
            },
        )

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res = await register_events(
        event_types=["stream"],
        all_public_streams=True,
        slim_presence=True,
        include_subscribers=True,
    )
    assert res["status"] == "success"
