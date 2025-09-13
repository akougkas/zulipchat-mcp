"""Basic tests for users_v25.manage_users to increase coverage.

Covers list, presence, and groups paths with a fake identity manager.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


class _Identity:
    class _Type:
        def __init__(self, value: str) -> None:
            self.value = value

    def __init__(self) -> None:
        self.type = self._Type("user")
        self.client = type("C", (), {"get_profile": lambda self: {"user_id": 1}})()


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_list_and_presence_and_groups(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_users(self):  # type: ignore[no-redef]
            return {"result": "success", "members": [{"id": 1}, {"id": 2}]}

        def update_presence(self, status, ping_only, new_user_input):  # type: ignore[no-redef]
            return {"result": "success"}

        def get_user_groups(self):  # type: ignore[no-redef]
            return {
                "result": "success",
                "user_groups": [
                    {"id": 10, "members": [1]},
                    {"id": 11, "members": [2]},
                ],
            }

    async def execute(tool, params, func, identity=None):
        # Provide get_current_identity() during execution
        mock_identity.get_current_identity = lambda: _Identity()
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # list
    res_list = await manage_users("list")
    assert (
        res_list["status"] == "success"
        and res_list["count"] == 2
        and res_list["identity_used"] == "user"
    )

    # presence
    res_presence = await manage_users("presence", status="active")
    assert (
        res_presence["status"] == "success" and res_presence["new_status"] == "active"
    )

    # groups
    res_groups = await manage_users("groups")
    assert res_groups["status"] == "success"
    assert any(
        g["id"] == 10 for g in res_groups["user_groups"]
    )  # filtered to include current user id 1
