"""Cover streams_v25 subscribe/unsubscribe by IDs paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_subscribe_unsubscribe_by_ids(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()

    async def exec_sub(tool, params, func, identity=None):
        class Client:
            def get_stream_id(self, stream_id):  # type: ignore[no-redef]
                return {"result": "success", "stream": {"name": "general"}}

            def add_subscriptions(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "subscribed": {"1": [1]}}

        return await func(Client(), params)

    mock_validator.validate_tool_params.return_value = {
        "operation": "subscribe",
        "stream_ids": [1],
    }
    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_sub)
    sub = await manage_streams(operation="subscribe", stream_ids=[1])
    assert sub["status"] == "success"

    async def exec_unsub(tool, params, func, identity=None):
        class Client:
            def get_stream_id(self, stream_id):  # type: ignore[no-redef]
                return {"result": "success", "stream": {"name": "general"}}

            def remove_subscriptions(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "removed": [1], "not_removed": []}

        return await func(Client(), params)

    mock_validator.validate_tool_params.return_value = {
        "operation": "unsubscribe",
        "stream_ids": [1],
    }
    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_unsub)
    unsub = await manage_streams(operation="unsubscribe", stream_ids=[1])
    assert unsub["status"] == "success"
