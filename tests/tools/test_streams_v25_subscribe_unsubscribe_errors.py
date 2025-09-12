"""Subscribe/unsubscribe error branches for manage_streams."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_subscribe_unsubscribe_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def add_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "error", "msg": "bad add"}
        def remove_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "error", "msg": "bad remove"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    sub = await manage_streams("subscribe", stream_names=["x"], authorization_errors_fatal=False)
    assert sub["status"] == "error" and "subscribe" in sub.get("operation", "subscribe")

    unsub = await manage_streams("unsubscribe", stream_names=["x"])
    assert unsub["status"] == "error" and unsub["operation"] == "unsubscribe"

