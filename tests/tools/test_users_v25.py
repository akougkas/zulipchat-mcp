"""Minimal tests for users_v25 tools (v2.5.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_list_basic(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "list",
        "client_gravatar": False,
        "include_custom_profile_fields": False,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_users(self, request=None):  # type: ignore[no-redef]
                return {"result": "success", "members": [{"full_name": "John"}]}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users(operation="list")
    assert res["status"] == "success"
    assert res["operation"] == "list"
    assert res["count"] == 1


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_mutually_exclusive_identity_error(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_managers.return_value = (Mock(), Mock(), Mock())
    res = await manage_users(operation="list", as_bot=True, as_admin=True)
    assert res["status"] == "error"
    assert "Cannot use both" in res["error"]
