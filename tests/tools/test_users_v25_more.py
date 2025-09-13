"""Additional targeted tests for users_v25 tools (v2.5.0).

Covers get/update/presence branches and error paths for avatar/profile_fields.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_get_by_id_success(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "get",
        "user_id": 42,
        "include_custom_profile_fields": False,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_user_by_id(self, uid, include_custom_profile_fields=False):  # type: ignore[no-redef]
                return {
                    "result": "success",
                    "user": {"user_id": uid, "full_name": "Jane"},
                }

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users(operation="get", user_id=42)
    assert res["status"] == "success"
    assert res["operation"] == "get"
    assert res["user"]["user_id"] == 42


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_get_by_email_success(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "get",
        "email": "user@example.com",
        "include_custom_profile_fields": True,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_user_by_email(self, email, include_custom_profile_fields=False):  # type: ignore[no-redef]
                return {"result": "success", "user": {"user_id": 100, "email": email}}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users(
        operation="get", email="user@example.com", include_custom_profile_fields=True
    )
    assert res["status"] == "success"
    assert res["user"]["email"] == "user@example.com"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_update_resolves_email_to_id(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "update",
        "email": "user@example.com",
        "full_name": "New Name",
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_user_by_email(self, email):  # type: ignore[no-redef]
                return {"result": "success", "user": {"user_id": 7, "email": email}}

            def update_user(self, user_id, **update_data):  # type: ignore[no-redef]
                assert user_id == 7
                assert "full_name" in update_data
                return {"result": "success"}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users(
        operation="update", email="user@example.com", full_name="New Name"
    )
    assert res["status"] == "success"
    assert res["operation"] == "update"
    assert res["user_id"] == 7
    assert "full_name" in res["updated_fields"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_presence_requires_status_and_success(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    # Error when status missing
    mock_managers.return_value = (Mock(), Mock(), Mock())
    err = await manage_users(operation="presence")
    assert err["status"] == "error"
    assert "status required" in err["error"]

    # Success flow
    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "presence",
        "status": "active",
        "client": "MCP",
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def update_presence(self, status, ping_only=False, new_user_input=True):  # type: ignore[no-redef]
                assert status == "active"
                return {"result": "success"}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await manage_users(operation="presence", status="active")
    assert ok["status"] == "success"
    assert ok["operation"] == "presence"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_avatar_and_profile_fields_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    # avatar without file -> error (simulate identity execution)
    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "avatar",
        "avatar_file": None,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            pass

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res = await manage_users(operation="avatar")
    assert res["status"] == "error"
    assert "avatar_file is required" in res["error"]

    # profile_fields without data -> get path should succeed
    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "profile_fields",
        "profile_field_data": None,
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_custom_profile_fields(self):  # type: ignore[no-redef]
                return {"result": "success", "custom_fields": [{"name": "Department"}]}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    ok = await manage_users(operation="profile_fields")
    assert ok["status"] == "success"
    assert ok["operation"] == "profile_fields"
    assert "available_fields" in ok
