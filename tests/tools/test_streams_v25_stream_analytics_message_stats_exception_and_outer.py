"""Exercise message_stats exception branch and outer exception handler in stream_analytics."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_message_stats_exception(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "x", "stream_id": 3}]}
        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"stream_id": sid, "name": "x"}}
        def get_messages(self, request):  # type: ignore[no-redef]
            raise RuntimeError("boom-messages")

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await stream_analytics(stream_name="x", include_message_stats=True, include_user_activity=False, include_topic_stats=False)
    assert out["status"] == "success" and "message_stats" in out and "error" in out["message_stats"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_outer_exception(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    async def exec_raise(tool, params, func, identity=None):
        raise RuntimeError("outer")

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_raise)

    err = await stream_analytics(stream_name="x")
    assert err["status"] == "error" and "outer" in err["error"]

