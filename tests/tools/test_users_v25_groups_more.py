"""More tests for users_v25 groups and group management actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_groups_success(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "groups",
    }

    # identity_manager.get_current_identity().client.get_profile()["user_id"]
    current_identity = Mock()
    current_identity.client.get_profile.return_value = {"user_id": 5}
    mock_identity.get_current_identity.return_value = current_identity

    async def execute(tool, params, func, identity=None):
        class Client:
            def get_user_groups(self):  # type: ignore[no-redef]
                return {
                    "result": "success",
                    "user_groups": [
                        {"id": 1, "name": "team", "members": [5, 6]},
                        {"id": 2, "name": "other", "members": [7]},
                    ],
                }
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users(operation="groups")
    assert res["status"] == "success"
    assert any(g["name"] == "team" for g in res["user_groups"])  # filtered includes current user


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_user_groups_update_delete_add_remove(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_user_groups

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    # update path resolves group by name
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "action": "update",
        "group_name": "team",
        "description": "updated",
    }

    class ClientUpdate:
        def get_user_groups(self):  # type: ignore[no-redef]
            return {"result": "success", "user_groups": [{"id": 3, "name": "team"}]}

        def update_user_group(self, gid, request):  # type: ignore[no-redef]
            assert gid == 3
            return {"result": "success"}

    async def exec_update(tool, params, func, identity=None):
        return await func(ClientUpdate(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_update)
    res_upd = await manage_user_groups(action="update", group_name="team", description="updated")
    assert res_upd["status"] == "success"
    assert res_upd["action"] == "update"

    # delete by id
    mock_validator.validate_tool_params.return_value = {
        "action": "delete",
        "group_id": 3,
    }

    class ClientDelete:
        def remove_user_group(self, gid):  # type: ignore[no-redef]
            assert gid == 3
            return {"result": "success"}

    async def exec_del(tool, params, func, identity=None):
        return await func(ClientDelete(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_del)
    res_del = await manage_user_groups(action="delete", group_id=3)
    assert res_del["status"] == "success"
    assert res_del["action"] == "delete"

    # add members
    mock_validator.validate_tool_params.return_value = {
        "action": "add_members",
        "group_id": 3,
        "members": [10, 11],
    }

    class ClientAdd:
        def update_user_group_members(self, gid, add=None, delete=None):  # type: ignore[no-redef]
            assert add == [10, 11]
            return {"result": "success"}

    async def exec_add(tool, params, func, identity=None):
        return await func(ClientAdd(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_add)
    res_add = await manage_user_groups(action="add_members", group_id=3, members=[10, 11])
    assert res_add["status"] == "success"
    assert res_add["action"] == "add_members"

    # remove members
    mock_validator.validate_tool_params.return_value = {
        "action": "remove_members",
        "group_id": 3,
        "members": [10],
    }

    class ClientRemove:
        def update_user_group_members(self, gid, add=None, delete=None):  # type: ignore[no-redef]
            assert delete == [10]
            return {"result": "success"}

    async def exec_remove(tool, params, func, identity=None):
        return await func(ClientRemove(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_remove)
    res_rem = await manage_user_groups(action="remove_members", group_id=3, members=[10])
    assert res_rem["status"] == "success"
    assert res_rem["action"] == "remove_members"

