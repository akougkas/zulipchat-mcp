"""stream_analytics variant: include_message_stats=True only."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_message_stats_only(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    now = int(datetime.now().timestamp())

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "x", "stream_id": 5}]}
        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"stream_id": sid, "name": "x"}}
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": [
                {"id": 1, "content": "hello", "timestamp": now, "sender_full_name": "A", "subject": "t"},
                {"id": 2, "content": "world", "timestamp": now, "sender_full_name": "B", "subject": "t"},
            ]}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await stream_analytics(
        stream_name="x",
        include_message_stats=True,
        include_user_activity=False,
        include_topic_stats=False,
    )
    assert out["status"] == "success"
    assert "message_stats" in out and "user_activity" not in out and "topic_stats" not in out

