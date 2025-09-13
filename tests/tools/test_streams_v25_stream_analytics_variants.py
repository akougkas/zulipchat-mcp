"""More variants for stream_analytics covering flags and errors."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_flags_and_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "x", "stream_id": 10}]}

        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"stream_id": sid, "name": "x"}}

        def get_messages(self, request):  # type: ignore[no-redef]
            # Return small set of messages
            now = int(datetime.now().timestamp())
            return {
                "result": "success",
                "messages": [
                    {
                        "id": 1,
                        "content": "hi",
                        "timestamp": now,
                        "sender_full_name": "A",
                        "subject": "t",
                    }
                ],
            }

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "error", "msg": "subs err"}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "error", "msg": "topics err"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await stream_analytics(
        stream_name="x",
        include_message_stats=False,
        include_user_activity=True,
        include_topic_stats=True,
    )
    assert out["status"] == "success"
    assert out["user_activity"]["error"] == "Could not retrieve subscriber information"
    assert out["topic_stats"]["error"] == "Could not retrieve topic statistics"

    # stream not found by name
    class ClientNF:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {"result": "success", "streams": []}

    async def exec_nf(tool, params, func, identity=None):
        return await func(ClientNF(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_nf)
    nf = await stream_analytics(stream_name="missing")
    assert nf["status"] == "error"
