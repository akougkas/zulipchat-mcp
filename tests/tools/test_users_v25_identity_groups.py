"""Users v2.5 identity switching and user group management tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_switch_identity_invalid_type(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import switch_identity

    mock_managers.return_value = (Mock(), Mock(), Mock())
    res = await switch_identity(identity="invalid", validate=False)
    assert res["status"] == "error"
    assert "Invalid identity type" in res["error"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_switch_identity_success_no_validate(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import switch_identity

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_identity.switch_identity.return_value = {
        "identity": "bot",
        "persistent": False,
        "capabilities": {"send": True},
        "email": "bot@example.com",
        "display_name": "Bot",
        "name": "bot",
    }
    mock_identity.get_available_identities.return_value = {
        "current": "user",
        "available": ["user", "bot", "admin"],
    }

    res = await switch_identity(identity="bot", validate=False)
    assert res["status"] == "success"
    assert res["switched_to"] == "bot"
    assert "available_identities" in res


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_user_groups_validation_and_create(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_user_groups

    # Validation: create without group_name
    mock_managers.return_value = (Mock(), Mock(), Mock())
    res_err = await manage_user_groups(action="create")
    assert res_err["status"] == "error"
    assert "group_name is required" in res_err["error"]

    # Create success
    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    async def execute(tool, params, func, identity=None):
        class Client:
            def create_user_group(self, request_data):  # type: ignore[no-redef]
                return {"result": "success", "id": 99}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await manage_user_groups(
        action="create", group_name="team", description="desc", members=[1, 2]
    )
    assert ok["status"] == "success"
    assert ok["action"] == "create"
    assert ok["group_id"] == 99
