"""Targeted tests for get_stream_info in streams_v25."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_get_stream_info_by_id_with_topics_and_subscribers(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import get_stream_info

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 123,
        "include_topics": True,
        "include_subscribers": True,
        "include_settings": True,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_stream_id(self, sid):  # type: ignore[no-redef]
                return {"result": "success", "stream": {"stream_id": sid, "name": "general"}}
            def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
                return {"result": "success", "topics": [{"name": "topic1"}]}
            def get_subscribers(self, stream_id):  # type: ignore[no-redef]
                return {"result": "success", "subscribers": [1, 2]}
            def get_subscriptions(self):  # type: ignore[no-redef]
                return {"result": "success", "subscriptions": [{"stream_id": 123, "is_muted": False}]}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await get_stream_info(stream_id=123, include_topics=True, include_subscribers=True, include_settings=True)
    assert res["status"] == "success"
    assert res["stream"]["stream_id"] == 123
    assert res["topics"][0]["name"] == "topic1"
    assert res["subscribers"] == [1, 2]
    assert res["subscription_settings"]["stream_id"] == 123


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_get_stream_info_by_name_not_found(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import get_stream_info

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "stream_name": "unknown",
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_streams(self, **kwargs):  # type: ignore[no-redef]
                return {"result": "success", "streams": [{"name": "general", "stream_id": 1}]}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await get_stream_info(stream_name="unknown")
    assert res["status"] == "error"
    assert "not found" in res["error"]

