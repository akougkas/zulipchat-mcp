"""Covers delete topic success and error branches in manage_topics."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_delete_success_and_error(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def delete_topic(self, stream_id, topic_name):  # type: ignore[no-redef]
            if topic_name == "ok":
                return {"result": "success"}
            return {"result": "error", "msg": "nope"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await manage_topics(stream_id=1, operation="delete", source_topic="ok")
    assert ok["status"] == "success" and ok["operation"] == "delete"

    err = await manage_topics(stream_id=1, operation="delete", source_topic="bad")
    assert err["status"] == "error" and err["operation"] == "delete"

