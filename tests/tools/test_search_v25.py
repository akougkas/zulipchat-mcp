"""Minimal tests for search_v25 tools (v2.5.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_advanced_search_basic(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "query": "deployment",
        "search_type": ["messages"],
        "narrow": [],
        "limit": 10,
    }

    async def execute(tool, params, func, identity=None):
        # Bypass internal logic for speed; return a normalized success
        return {"status": "success", "results": [], "count": 0}

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await advanced_search(query="deployment", limit=10)
    assert res["status"] == "success"
    assert res["count"] == 0


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_basic(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {
        "metric": "activity",
        "narrow": [],
        "format": "summary",
    }

    async def execute(tool, params, func, identity=None):
        return {"status": "success", "metric": "activity", "summary": {}}

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await analytics(metric="activity")
    assert res["status"] == "success"
    assert res["metric"] == "activity"

