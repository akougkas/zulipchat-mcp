"""Additional success-path tests for streams_v25 subscribe/unsubscribe/update."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_update_multiple_properties(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "update",
        "stream_ids": [10],
        "properties": {"description": "New desc", "invite_only": True},
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def update_stream(self, stream_id, **kwargs):  # type: ignore[no-redef]
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams(operation="update", stream_ids=[10], properties={"description": "New desc", "invite_only": True})
    assert res["status"] == "success"
    assert res["operation"] == "update"
    # Two results, one per property
    assert len(res["results"]) == 2


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_subscribe_and_unsubscribe_by_names(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    # Subscribe
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "subscribe",
        "stream_names": ["general", "dev"],
        "authorization_errors_fatal": True,
    }

    class SubClient:
        def add_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "subscribed": {"general": [1], "dev": [2]}}

    async def exec_sub(tool, params, func, identity=None):
        return await func(SubClient(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_sub)
    sub_res = await manage_streams(operation="subscribe", stream_names=["general", "dev"])
    assert sub_res["status"] == "success"
    assert "subscribed" in sub_res

    # Unsubscribe
    mock_validator.validate_tool_params.return_value = {
        "operation": "unsubscribe",
        "stream_names": ["general"],
    }

    class UnsubClient:
        def remove_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "removed": ["general"], "not_removed": []}

    async def exec_unsub(tool, params, func, identity=None):
        return await func(UnsubClient(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_unsub)
    unsub_res = await manage_streams(operation="unsubscribe", stream_names=["general"])
    assert unsub_res["status"] == "success"
    assert unsub_res["removed"] == ["general"]

