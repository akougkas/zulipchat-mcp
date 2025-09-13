"""Tests for streams_v25.manage_streams subscribe/unsubscribe/list paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_subscribe_unsubscribe_list(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, include_subscribed=True):  # type: ignore[no-redef]
            return {
                "result": "success",
                "streams": [{"name": "general"}, {"name": "dev"}],
            }

        def get_stream_id(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "stream": {"name": f"s{stream_id}"}}

        def add_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {
                "result": "success",
                "subscribed": {"general": [1]},
                "already_subscribed": {},
                "unauthorized": [],
            }

        def remove_subscriptions(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "removed": ["general"], "not_removed": []}

        def create_streams(self, **kwargs):  # type: ignore[no-redef]
            return {
                "result": "success",
                "subscribed": {"new": [1]},
                "already_subscribed": {},
                "unauthorized": [],
            }

        def update_stream(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success"}

        def delete_stream(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # subscribe by name
    sub = await manage_streams(
        "subscribe",
        stream_names=["general"],
        principals=["u@e"],
        authorization_errors_fatal=False,
    )
    assert sub["status"] == "success" and sub["operation"] == "subscribe"

    # unsubscribe by id (uses get_stream_id to resolve names)
    unsub = await manage_streams("unsubscribe", stream_ids=[1])
    assert unsub.get("operation") == "unsubscribe"

    # update
    upd = await manage_streams(
        "update", stream_ids=[1, 2], properties={"is_web_public": True}
    )
    assert upd["status"] == "success" and upd["operation"] == "update"

    # delete
    dele = await manage_streams("delete", stream_ids=[1, 2])
    assert dele["status"] == "success" and dele["operation"] == "delete"

    # create
    cre = await manage_streams(
        "create", stream_names=["new"], properties={"description": "d"}
    )
    assert cre["status"] == "success" and cre["operation"] == "create"
