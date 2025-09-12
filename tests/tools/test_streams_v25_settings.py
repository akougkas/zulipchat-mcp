"""Tests for streams_v25.manage_stream_settings operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_stream_settings_all_ops(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_stream_settings

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()

    class Client:
        def get_subscriptions(self):  # type: ignore[no-redef]
            return {"result": "success", "subscriptions": [{"stream_id": 1, "color": "#ccc"}]}
        def update_subscription_settings(self, updates):  # type: ignore[no-redef]
            return {"result": "success"}
        def update_stream(self, stream_id, **permission_updates):  # type: ignore[no-redef]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    # get
    g = await manage_stream_settings(1, "get")
    assert g["status"] == "success" and g["operation"] == "get"

    # update appearance
    u = await manage_stream_settings(1, "update", color="#ff6600", pin_to_top=True)
    assert u["status"] == "success" and u["operation"] == "update"

    # notifications
    n = await manage_stream_settings(1, "notifications", notification_settings={"desktop_notifications": True})
    assert n["status"] == "success" and n["operation"] == "notifications"

    # permissions
    p = await manage_stream_settings(1, "permissions", permission_updates={"is_public": True})
    assert p["status"] == "success" and p["operation"] == "permissions"

    # invalid id
    bad = await manage_stream_settings(0, "get")
    assert bad["status"] == "error"

    # error branches: update with no updates
    err_upd = await manage_stream_settings(1, "update")
    assert err_upd["status"] == "error" and "No updates" in err_upd["error"]

    # error branch: notifications without settings
    err_notif = await manage_stream_settings(1, "notifications")
    assert err_notif["status"] == "error" and "notification_settings" in err_notif["error"]

    # error branch: permissions without updates
    err_perm = await manage_stream_settings(1, "permissions")
    assert err_perm["status"] == "error" and "permission_updates" in err_perm["error"]

    # API error paths
    class ErrClient:
        def get_subscriptions(self):  # type: ignore[no-redef]
            return {"result": "error", "msg": "no subs"}
        def update_subscription_settings(self, updates):  # type: ignore[no-redef]
            return {"result": "error", "msg": "bad update"}
        def update_stream(self, stream_id, **permission_updates):  # type: ignore[no-redef]
            return {"result": "error", "msg": "bad perms"}

    async def exec_err(tool, params, func, identity=None):
        return await func(ErrClient(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_err)
    bad_get = await manage_stream_settings(1, "get")
    assert bad_get["status"] == "error"
    bad_notif = await manage_stream_settings(1, "notifications", notification_settings={"desktop_notifications": True})
    assert bad_notif["status"] == "error"
    bad_perm = await manage_stream_settings(1, "permissions", permission_updates={"is_web_public": True})
    assert bad_perm["status"] == "error"
