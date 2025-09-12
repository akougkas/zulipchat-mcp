"""Edge coverage for analytics: stats/detailed, chart for sentiment, topics grouping, participation detailed overall."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _msg(ts_offset: int, sender="Alice", stream="general", content="Hello", subject="topic"):
    return {
        "id": ts_offset,
        "sender_full_name": sender,
        "display_recipient": stream,
        "timestamp": int((datetime.now() - timedelta(seconds=ts_offset)).timestamp()),
        "content": content,
        "subject": subject,
    }


class _ClientBase:
    def get_messages(self, request):  # type: ignore[no-redef]
        return self.get_messages_raw(**request)

    def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
        raise NotImplementedError


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_activity_detailed_and_sentiment_chart(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    msgs = [
        _msg(10, sender="A", stream="s1"),
        _msg(20, sender="B", stream="s2"),
        _msg(30, sender="A", stream="s1"),
    ]

    class Client(_ClientBase):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # activity detailed with stats and group_by day
    act = await analytics(metric="activity", group_by="day", format="detailed", include_stats=True)
    assert act["status"] == "success" and any("Total messages analyzed" in x for x in act.get("detailed_insights", []))

    # sentiment chart data with hour grouping
    sent = await analytics(metric="sentiment", group_by="hour", format="chart_data")
    assert sent["status"] == "success" and "chart_data" in sent and isinstance(sent["chart_data"].get("series", []), list)


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_topics_and_participation_detailed(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    msgs = [
        _msg(5, sender="Alice", stream="general", content="project meeting plan"),
        _msg(6, sender="Bob", stream="dev", content="fix bug error logs"),
        _msg(7, sender="Alice", stream="dev", content="release planning deploy"),
    ]

    class Client(_ClientBase):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # topics detailed with group_by day (exercise detailed insights: top topic + top words)
    top = await analytics(metric="topics", group_by="day", format="detailed")
    assert top["status"] == "success" and "topics" in top["data"] and isinstance(top.get("detailed_insights", []), list)

    # participation detailed with overall grouping (no group_by)
    part = await analytics(metric="participation", format="detailed")
    assert part["status"] == "success" and any("Average message length" in x for x in part.get("detailed_insights", []))


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_sentiment_negative_insight(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    msgs = [
        _msg(5, content="this is bad and terrible error"),
        _msg(6, content="awful bug and bad experience"),
        _msg(7, content="bad"),
        _msg(8, content="good"),
    ]

    class Client(_ClientBase):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await analytics(metric="sentiment", format="detailed")
    assert res["status"] == "success"
    # Ensure the negative sentiment insight branch triggers
    assert any("negative sentiment" in x for x in res.get("detailed_insights", []))
