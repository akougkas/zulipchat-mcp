"""Tests for users_v25.manage_user_groups actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_user_groups_crud_and_members(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_user_groups

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    class Client:
        def create_user_group(self, data):  # type: ignore[no-redef]
            return {"result": "success", "id": 7}

        def get_user_groups(self):  # type: ignore[no-redef]
            return {"result": "success", "user_groups": [{"id": 7, "name": "dev"}]}

        def update_user_group(self, gid, data):  # type: ignore[no-redef]
            return {"result": "success"}

        def remove_user_group(self, gid):  # type: ignore[no-redef]
            return {"result": "success"}

        def update_user_group_members(self, gid, add=None, delete=None):  # type: ignore[no-redef]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # create
    c = await manage_user_groups(
        "create", group_name="dev", description="d", members=[1, 2]
    )
    assert c["status"] == "success" and c["group_id"] == 7

    # update by name
    u = await manage_user_groups("update", group_name="dev", description="nd")
    assert u["status"] == "success" and u["action"] == "update"

    # add members
    a = await manage_user_groups("add_members", group_name="dev", members=[3])
    assert a["status"] == "success" and a["count"] == 1

    # remove members
    r = await manage_user_groups("remove_members", group_name="dev", members=[3])
    assert r["status"] == "success" and r["count"] == 1

    # delete
    d = await manage_user_groups("delete", group_name="dev")
    assert d["status"] == "success" and d["action"] == "delete"
