"""More analytics coverage for participation/topics with chart data."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


def _m(stream: str, topic: str, sender: str, content: str):
    return {
        "id": hash((stream, topic, sender, content)) & 0xFFFF,
        "display_recipient": stream,
        "subject": topic,
        "sender_full_name": sender,
        "content": content,
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_participation_chart_by_stream(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    msgs = [
        _m("general", "t1", "Alice", "hello world"),
        _m("general", "t1", "Bob", "another message"),
        _m("dev", "deploy", "Alice", "deploy now"),
    ]

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await analytics(
        metric="participation",
        format="chart_data",
        group_by="stream",
        include_stats=True,
    )
    assert out["status"] == "success" and "chart_data" in out


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_topics_chart_by_stream(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    msgs = [
        _m("general", "planning", "Alice", "meeting project plan"),
        _m("dev", "bugs", "Bob", "bug fix release"),
        _m("dev", "bugs", "Alice", "error logs question"),
    ]

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await analytics(metric="topics", group_by="stream", format="chart_data")
    assert out["status"] == "success"
    assert "topics" in out["data"] and "chart_data" in out
