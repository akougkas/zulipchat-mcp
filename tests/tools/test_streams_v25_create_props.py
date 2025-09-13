"""Coverage for streams_v25 create with extended properties/options."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_create_with_properties_and_options(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "create",
        "stream_names": ["general"],
        "properties": {"description": "desc"},
        "invite_only": True,
        "announce": True,
        "authorization_errors_fatal": True,
        "principals": ["user@example.com"],
        "history_public_to_subscribers": True,
        "stream_post_policy": 1,
        "message_retention_days": 30,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def add_subscriptions(self, **kwargs):  # type: ignore[no-redef]
                # ensure options passed through
                assert kwargs.get("announce") is True
                assert kwargs.get("authorization_errors_fatal") is True
                return {"result": "success", "subscribed": {"general": [1]}}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams(
        operation="create",
        stream_names=["general"],
        properties={"description": "desc"},
        invite_only=True,
        announce=True,
        principals=["user@example.com"],
        history_public_to_subscribers=True,
        stream_post_policy=1,
        message_retention_days=30,
    )
    assert res["status"] == "success"
    assert "subscribed" in res
