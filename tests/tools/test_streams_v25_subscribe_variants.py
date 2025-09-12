"""Subscribe/unsubscribe variants for streams_v25.manage_streams."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_subscribe_ids_and_unsubscribe_names(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_stream_id(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"name": f"s{stream_id}"}}
        def add_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "subscribed": {"s1": [1]}}
        def remove_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "removed": ["dev"], "not_removed": []}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    sub = await manage_streams("subscribe", stream_ids=[1])
    assert sub["status"] == "success" and sub["operation"] == "subscribe"

    unsub = await manage_streams("unsubscribe", stream_names=["dev"])
    assert unsub["status"] == "success" and unsub["operation"] == "unsubscribe"

