"""Tests for stream_analytics focusing on KeyError-suspect paths and subscribers shape."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_populates_stream_name_and_handles_weird_stream_info(
    mock_managers,
) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {
                "result": "success",
                "streams": [{"name": "general", "stream_id": 1}],
            }

        # Simulate unexpected shape without a 'stream' key
        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "name": "general", "stream_id": sid}

        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            # Ensure we used a valid name for the narrow
            assert kwargs["narrow"][0]["operand"] == "general"
            return {"result": "success", "messages": []}

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "subscribers": {"oops": "not-a-list"}}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "topics": []}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await stream_analytics(stream_name="general")
    assert res["status"] == "success"
    # We should have a stream_name populated and user_activity computed safely
    assert res.get("stream_name") == "general"
    assert res.get("user_activity", {}).get("total_subscribers") == 0


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_handles_standard_stream_shape_and_subs_list(
    mock_managers,
) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {
                "result": "success",
                "streams": [{"name": "dev", "stream_id": 2}],
            }

        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"name": "dev", "stream_id": sid}}

        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": [{"content": "hi"}]}

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "subscribers": [10, 11]}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {
                "result": "success",
                "topics": [{"name": "t", "max_id": 5, "min_id": 1}],
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await stream_analytics(stream_name="dev")
    assert res["status"] == "success"
    assert res.get("message_stats", {}).get("recent_message_count") == 1
    assert res.get("user_activity", {}).get("total_subscribers") == 2
    assert res.get("topic_stats", {}).get("total_topics") == 1


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_topic_stats_exception_is_caught(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "ops", "stream_id": 7}]}

        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"name": "ops", "stream_id": sid}}

        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": []}

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "error", "msg": "denied"}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            raise RuntimeError("boom")

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await stream_analytics(stream_name="ops")
    assert res["status"] == "success"
    assert "error" in res.get("topic_stats", {})


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_stream_analytics_message_stats_error_branch(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import stream_analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, include_public=True):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "eng", "stream_id": 8}]}

        def get_stream_id(self, sid):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"name": "eng", "stream_id": sid}}

        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "error", "msg": "rate limited"}

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "subscribers": []}

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "topics": []}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await stream_analytics(stream_name="eng")
    assert res["status"] == "success"
    assert "error" in res.get("message_stats", {})
