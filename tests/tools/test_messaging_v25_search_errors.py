"""Extra guard tests for messaging_v25.search_messages error paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_search_messages_invalid_params(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import search_messages

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    # invalid anchor
    res1 = await search_messages(anchor=-5)
    assert res1["status"] == "error" and "Invalid message ID" in res1["error"]

    # too many messages
    res2 = await search_messages(num_before=6000, num_after=10)
    assert res2["status"] == "error" and "Too many" in res2["error"]

