"""Cover analytics no-messages early return and outer exception path."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_no_messages(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": []}

        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return self.get_messages(kwargs)

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await analytics(metric="activity")
    assert res["status"] == "success" and "No messages found" in res["data"].get(
        "message", ""
    )


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_outer_exception(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    async def execute_raises(tool, params, func, identity=None):
        raise RuntimeError("boom")

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute_raises)

    out = await analytics(metric="activity")
    assert out["status"] == "error" and "Failed to execute analytics" in out["error"]
