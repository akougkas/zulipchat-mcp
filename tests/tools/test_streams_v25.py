"""Minimal tests for streams_v25 tools (v2.5.0).

Focused on happy-path list operation with mocks, fast and deterministic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_list_basic(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    mock_config = Mock()
    mock_identity = Mock()
    mock_validator = Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    # Validation returns params as-is
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "operation": "list",
        "include_public": True,
        "include_subscribed": True,
    }

    # Execute returns a successful list
    async def execute(tool, params, func):
        class Client:
            def get_streams(self, **kwargs):
                return {"result": "success", "streams": [{"name": "general"}]}

        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_streams(
        operation="list", include_public=True, include_subscribed=True
    )
    assert res["status"] == "success"
    assert res["operation"] == "list"
    assert isinstance(res["streams"], list)
