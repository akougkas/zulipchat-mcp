"""Targeted tests for streams_v25.stream_analytics to lift coverage.

Covers successful path resolving by stream_name and collecting
message_stats, user_activity, and topic_stats.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_success_by_name(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    now = int(datetime.now().timestamp())

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {
                "result": "success",
                "streams": [{"name": "general", "stream_id": 10}],
            }

        def get_stream_id(self, stream_id):  # type: ignore[no-redef]
            assert stream_id == 10
            return {"result": "success", "stream": {"stream_id": 10, "name": "general"}}

        def get_messages(self, request):  # type: ignore[no-redef]
            return {
                "result": "success",
                "messages": [
                    {"id": 1, "content": "hello", "timestamp": now},
                    {"id": 2, "content": "world", "timestamp": now},
                ],
            }

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "subscribers": [1, 2, 3]}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {
                "result": "success",
                "topics": [
                    {"name": "t1", "max_id": 20, "min_id": 10},
                    {"name": "t2", "max_id": 30, "min_id": 25},
                ],
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await stream_analytics(stream_name="general")
    assert res["status"] == "success"
    assert res["stream_id"] == 10
    assert "message_stats" in res and "user_activity" in res and "topic_stats" in res
