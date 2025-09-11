"""Users v2.5 switch_identity error handling test."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.users_v25._get_managers")
async def test_switch_identity_exception_path(mock_managers) -> None:
    from zulipchat_mcp.tools.users_v25 import switch_identity

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    def boom(*args, **kwargs):
        raise RuntimeError("bad creds")

    mock_identity.switch_identity.side_effect = boom

    res = await switch_identity(identity="admin", validate=True)
    assert res["status"] == "error"
    assert "Failed to switch to" in res["error"]

