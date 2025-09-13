"""Error branches for get_stream_info optional sections."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_get_stream_info_topics_and_subscribers_error(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import get_stream_info

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_stream_id(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"stream_id": 1, "name": "general"}}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "error", "msg": "topics failed"}

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "error", "msg": "subs failed"}

        def get_subscriptions(self):  # type: ignore[no-redef]
            return {"result": "error", "msg": "subs list failed"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await get_stream_info(
        stream_id=1,
        include_topics=True,
        include_subscribers=True,
        include_settings=True,
    )
    assert out["status"] == "success"
    assert out.get("topics_error") == "topics failed"
    assert out.get("subscribers_error") == "subs failed"
    assert "subscription_settings" not in out  # because get_subscriptions failed
