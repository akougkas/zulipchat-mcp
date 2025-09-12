"""Error-path tests for users_v25.manage_users."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_manage_users_identity_conflict_error(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import manage_users

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    res = await manage_users("list", as_bot=True, as_admin=True)
    assert res["status"] == "error" and "cannot use both" in res["error"].lower()

