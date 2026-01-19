"""Tests for tools/ai_analytics.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.ai_analytics import (
    analyze_stream_with_llm,
    analyze_team_activity_with_llm,
    get_daily_summary,
    intelligent_report_generator,
)


class TestAIAnalytics:
    """Tests for AI analytics tools."""

    @pytest.fixture
    def mock_deps(self):
        with (
            patch("src.zulipchat_mcp.tools.ai_analytics.ConfigManager"),
            patch(
                "src.zulipchat_mcp.tools.ai_analytics.ZulipClientWrapper"
            ) as mock_wrapper,
            patch(
                "src.zulipchat_mcp.tools.search.search_messages", new_callable=AsyncMock
            ) as mock_search,
        ):

            client = MagicMock()
            mock_wrapper.return_value = client
            yield client, mock_search

    @pytest.mark.asyncio
    async def test_get_daily_summary(self, mock_deps):
        """Test get_daily_summary."""
        client, _ = mock_deps
        client.get_daily_summary.return_value = {"total": 10}

        result = await get_daily_summary(streams=["s1"], hours_back=12)

        assert result["status"] == "success"
        assert result["summary"]["total"] == 10
        client.get_daily_summary.assert_called_with(streams=["s1"], hours_back=12)

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_success(self, mock_deps):
        """Test analyze_stream_with_llm returns data for LLM analysis."""
        _, mock_search = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [
                {"sender": "Alice", "content": "Hello", "topic": "general", "timestamp": 123}
            ],
        }

        result = await analyze_stream_with_llm(
            stream_name="general", analysis_type="summary"
        )

        assert result["status"] == "success"
        assert result["stream"] == "general"
        assert result["message_count"] == 1
        assert "data_summary" in result
        assert "analysis_prompt" in result
        assert "instruction" in result

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_search_failed(self, mock_deps):
        """Test analyze_stream_with_llm search failure."""
        _, mock_search = mock_deps
        mock_search.return_value = {"status": "error"}

        result = await analyze_stream_with_llm("general", "summary")

        assert result["status"] == "error"
        assert "Failed to fetch stream data" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_no_messages(self, mock_deps):
        """Test analyze_stream_with_llm with no messages."""
        _, mock_search = mock_deps
        mock_search.return_value = {"status": "success", "messages": []}

        result = await analyze_stream_with_llm("general", "summary")

        assert result["status"] == "success"
        assert result["message_count"] == 0
        assert result["analysis_prompt"] is None

    @pytest.mark.asyncio
    async def test_analyze_team_activity_with_llm(self, mock_deps):
        """Test analyze_team_activity_with_llm returns data for LLM analysis."""
        _, mock_search = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work", "topic": "proj"}],
        }

        result = await analyze_team_activity_with_llm(
            team_streams=["s1", "s2"], analysis_focus="productivity"
        )

        assert result["status"] == "success"
        assert result["total_messages"] == 2  # 1 per stream * 2 streams
        assert result["streams_analyzed"] == 2
        assert "data_summary" in result
        assert "analysis_prompt" in result

    @pytest.mark.asyncio
    async def test_intelligent_report_generator(self, mock_deps):
        """Test intelligent_report_generator returns data with report template."""
        _, mock_search = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work", "topic": "proj"}],
        }

        result = await intelligent_report_generator(
            report_type="standup", target_streams=["s1"]
        )

        assert result["status"] == "success"
        assert result["report_type"] == "standup"
        assert "report_template" in result
        assert "Daily Standup Report" in result["report_template"]
        assert "instruction" in result
