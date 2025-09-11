"""Tests for streams_v25.manage_stream_settings operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_stream_settings_get_and_update(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_stream_settings

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()

    # Get
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "get",
    }

    async def exec_get(tool, params, func, identity=None):
        class Client:
            def get_subscriptions(self):  # type: ignore[no-redef]
                return {"result": "success", "subscriptions": [{"stream_id": 10, "is_muted": False}]}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_get)
    res_get = await manage_stream_settings(stream_id=10, operation="get")
    assert res_get["status"] == "success"
    assert res_get["operation"] == "get"

    # Update appearance
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "update",
    }

    async def exec_update(tool, params, func, identity=None):
        class Client:
            def update_subscription_settings(self, settings):  # type: ignore[no-redef]
                assert settings[0]["stream_id"] == 10
                assert settings[0]["color"] == "#ff6600"
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_update)
    res_upd = await manage_stream_settings(stream_id=10, operation="update", color="#ff6600")
    assert res_upd["status"] == "success"
    assert res_upd["operation"] == "update"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_stream_settings_notifications_and_permissions(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_stream_settings

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()

    # Notifications
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "notifications",
    }

    async def exec_notif(tool, params, func, identity=None):
        class Client:
            def update_subscription_settings(self, settings):  # type: ignore[no-redef]
                # expect property/value mapping
                assert settings[0]["property"] == "push_notifications"
                assert settings[0]["value"] is True
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_notif)
    res_not = await manage_stream_settings(stream_id=10, operation="notifications", notification_settings={"push_notifications": True})
    assert res_not["status"] == "success"
    assert res_not["operation"] == "notifications"

    # Permissions
    mock_validator.validate_tool_params.return_value = {
        "stream_id": 10,
        "operation": "permissions",
    }

    async def exec_perm(tool, params, func, identity=None):
        class Client:
            def update_stream(self, stream_id, **permission_updates):  # type: ignore[no-redef]
                assert stream_id == 10
                assert permission_updates == {"is_announcement_only": True}
                return {"result": "success"}
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_perm)
    res_perm = await manage_stream_settings(stream_id=10, operation="permissions", permission_updates={"is_announcement_only": True})
    assert res_perm["status"] == "success"
    assert res_perm["operation"] == "permissions"

