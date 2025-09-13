"""Additional success test for get_stream_info by name with extras."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_get_stream_info_by_name_success(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import get_stream_info

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True, force_fresh=False):  # type: ignore[no-redef]
            return {
                "result": "success",
                "streams": [{"name": "general", "stream_id": 1}],
            }

        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "topics": [{"name": "t"}]}

        def get_subscribers(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "subscribers": [1]}

        def get_subscriptions(self):  # type: ignore[no-redef]
            return {
                "result": "success",
                "subscriptions": [{"stream_id": 1, "pin_to_top": True}],
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await get_stream_info(
        stream_name="general",
        include_topics=True,
        include_subscribers=True,
        include_settings=True,
    )
    assert res["status"] == "success" and res["stream"]["name"] == "general"
