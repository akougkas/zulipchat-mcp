"""Tests for streams_v25.manage_topics operations (list/move/mark_read/mute/unmute)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_list_and_truncate(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "topics": [{"name": f"t{i}"} for i in range(10)]}

    async def execute(tool, params, func, identity=None):
        # Pass through validated params unchanged; manage_topics already supplies max_results
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await manage_topics(stream_id=1, operation="list", max_results=5)
    assert res["status"] == "success" and res["count"] == 5 and res["truncated"] is True


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_move_mark_read_mute_unmute(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": [{"id": 99}]}
        def update_message(self, payload):  # type: ignore[no-redef]
            return {"result": "success"}
        def mark_topic_as_read(self, stream_id, topic_name):  # type: ignore[no-redef]
            return {"result": "success"}
        def mute_topic(self, stream_id, topic):  # type: ignore[no-redef]
            return {"result": "success"}
        def unmute_topic(self, stream_id, topic):  # type: ignore[no-redef]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # Move
    mv = await manage_topics(stream_id=1, operation="move", source_topic="a", target_topic="b")
    assert mv["status"] == "success" and mv["operation"] == "move"

    # Mark read
    mr = await manage_topics(stream_id=1, operation="mark_read", source_topic="a")
    assert mr["status"] == "success"

    # Mute/Unmute
    mt = await manage_topics(stream_id=1, operation="mute", source_topic="a")
    assert mt["status"] == "success"
    um = await manage_topics(stream_id=1, operation="unmute", source_topic="a")
    assert um["status"] == "success"
