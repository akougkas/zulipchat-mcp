"""Additional analytics tests for search_v25: sentiment, topics, participation."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _msg(
    ts_offset: int, sender="Alice", stream="general", content="Hello", subject="topic"
):
    return {
        "id": 1,
        "sender_full_name": sender,
        "display_recipient": stream,
        "timestamp": int(datetime.now().timestamp()) - ts_offset,
        "content": content,
        "subject": subject,
    }


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_sentiment_detailed_by_user(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {
                "result": "success",
                "messages": [
                    _msg(5, sender="Alice", content="I love this great feature!"),
                    _msg(10, sender="Bob", content="This is a bad problem"),
                    _msg(15, sender="Alice", content="Thanks! awesome work"),
                ],
            }

        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages(
                {
                    "anchor": anchor,
                    "num_before": num_before,
                    "num_after": num_after,
                    "narrow": narrow or [],
                }
            )

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await analytics(metric="sentiment", group_by="user", format="detailed")
    assert res["status"] == "success"
    assert "sentiment" in res["data"]
    assert any("Overall sentiment" in line for line in res.get("detailed_insights", []))


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_topics_group_by_stream(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {
                "result": "success",
                "messages": [
                    _msg(
                        5,
                        stream="general",
                        content="Project deadline and meeting notes",
                    ),
                    _msg(6, stream="dev", content="Fix bug and error logs"),
                    _msg(7, stream="dev", content="Release planning and deploy"),
                ],
            }

        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages(
                {
                    "anchor": anchor,
                    "num_before": num_before,
                    "num_after": num_after,
                    "narrow": narrow or [],
                }
            )

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await analytics(metric="topics", group_by="stream")
    assert res["status"] == "success"
    assert "topics" in res["data"]
    assert "grouped_topics" in res["data"]


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_analytics_participation_chart_overall(mock_managers) -> None:
    from zulipchat_mcp.tools.search_v25 import analytics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {
                "result": "success",
                "messages": [
                    _msg(
                        5,
                        sender="Alice",
                        content="Hello world",
                        subject="t1",
                        stream="general",
                    ),
                    _msg(
                        6,
                        sender="Bob",
                        content="Another message here",
                        subject="t2",
                        stream="dev",
                    ),
                ],
            }

        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages(
                {
                    "anchor": anchor,
                    "num_before": num_before,
                    "num_after": num_after,
                    "narrow": narrow or [],
                }
            )

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await analytics(metric="participation", format="chart_data")
    assert res["status"] == "success"
    assert "participation" in res["data"]
    assert "series" in res.get("chart_data", {})
