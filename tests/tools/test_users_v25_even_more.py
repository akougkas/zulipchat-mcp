"""Even more users_v25 tests: avatar upload and profile fields update."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_avatar_upload_success(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "avatar",
        "avatar_file": b"bytes",
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def upload_avatar(self, avatar_file):  # type: ignore[no-redef]
                assert avatar_file == b"bytes"
                return {"result": "success"}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users(operation="avatar", avatar_file=b"bytes")
    assert res["status"] == "success"
    assert res["operation"] == "avatar"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_profile_fields_update_success(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "profile_fields",
        "profile_field_data": {"department": "Eng"},
    }

    async def execute(tool, params, func, identity=None):
        class Client:
            def update_profile_fields(self, data):  # type: ignore[no-redef]
                assert data == {"department": "Eng"}
                return {"result": "success"}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users(
        operation="profile_fields", profile_field_data={"department": "Eng"}
    )
    assert res["status"] == "success"
    assert res["operation"] == "profile_fields"
    assert "updated_fields" in res
