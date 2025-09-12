"""Tests for users_v25.manage_users update path."""

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
async def test_manage_users_update_by_email(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_user_by_email(self, email, include_custom_profile_fields=False):  # type: ignore[no-redef]
            return {"result": "success", "user": {"user_id": 5}}
        def update_user(self, user_id, **update_data):  # type: ignore[no-redef]
            assert user_id == 5 and "full_name" in update_data
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        mock_identity.get_current_identity = lambda: _Identity()
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_users("update", email="x@example.com", full_name="New Name")
    assert res["status"] == "success" and res["user_id"] == 5 and "full_name" in res["updated_fields"]

