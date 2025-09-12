"""Cover message_stats error and exception branches in stream_analytics."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_message_stats_error_and_exceptions(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "x", "stream_id": 7}]}
        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"stream_id": sid, "name": "x"}}
        def get_messages(self, request):  # type: ignore[no-redef]
            # First force an error branch
            return {"result": "error", "msg": "bad"}
        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            raise RuntimeError("subs boom")
        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            raise RuntimeError("topics boom")

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await stream_analytics(stream_name="x", include_message_stats=True, include_user_activity=True, include_topic_stats=True)
    assert out["status"] == "success"
    assert out.get("message_stats", {}).get("error") == "Could not retrieve message statistics"
    assert "Failed to get user activity" in out.get("user_activity", {}).get("error", "")
    assert "Failed to get topic stats" in out.get("topic_stats", {}).get("error", "")
