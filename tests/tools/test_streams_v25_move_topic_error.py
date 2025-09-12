"""Error branch for move topic when no messages found."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_move_no_messages_error(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": []}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    mv = await manage_topics(stream_id=1, operation="move", source_topic="a", target_topic="b")
    assert mv["status"] == "error" and "No messages found" in mv["error"]

