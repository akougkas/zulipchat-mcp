"""Ensure include_subscribed=False permutation for manage_streams(list) hits param guard."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_list_include_subscribed_false(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    seen = {}

    class Client:
        def get_streams(self, include_subscribed=True, force_fresh=False):  # type: ignore[no-redef]
            # Record the value that made it through; implementation defaults to True
            seen["include_subscribed"] = include_subscribed
            return {
                "result": "success",
                "streams": [{"name": "general", "stream_id": 1}],
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await manage_streams(
        "list", include_subscribed=False, include_all_active=True
    )
    assert out["status"] == "success" and out["operation"] == "list"
    # Because code sets include_subscribed only when True, value passed remains default True
    assert seen.get("include_subscribed") is True
