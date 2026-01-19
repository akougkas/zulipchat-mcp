"""Tests for tools/ai_analytics.py."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mcp.types import TextContent, ImageContent
from src.zulipchat_mcp.tools.ai_analytics import (
    get_daily_summary,
    analyze_stream_with_llm,
    analyze_team_activity_with_llm,
    intelligent_report_generator,
)


class TestAIAnalytics:
    """Tests for AI analytics tools."""

    @pytest.fixture
    def mock_deps(self):
        with patch("src.zulipchat_mcp.tools.ai_analytics.ConfigManager"), \
             patch("src.zulipchat_mcp.tools.ai_analytics.ZulipClientWrapper") as mock_wrapper, \
             patch("src.zulipchat_mcp.tools.search.search_messages", new_callable=AsyncMock) as mock_search:

            client = MagicMock()
            mock_wrapper.return_value = client
            yield client, mock_search

    @pytest.fixture
    def mock_ctx(self):
        ctx = MagicMock()
        ctx.sample = AsyncMock()
        return ctx

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
    async def test_analyze_stream_with_llm_success(self, mock_deps, mock_ctx):
        """Test analyze_stream_with_llm success."""
        client, mock_search = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Hello"}]
        }

        mock_ctx.sample.return_value = MagicMock(content=[TextContent(type="text", text="Analysis result")])

        result = await analyze_stream_with_llm(
            stream_name="general",
            analysis_type="summary",
            ctx=mock_ctx
        )

        assert result["status"] == "success"
        assert result["analysis"] == "Analysis result"
        mock_ctx.sample.assert_called()


    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_search_failed(self, mock_deps, mock_ctx):
        """Test analyze_stream_with_llm search failure."""
        _, mock_search = mock_deps
        mock_search.return_value = {"status": "error"}

        result = await analyze_stream_with_llm("general", "summary", ctx=mock_ctx)

        assert result["status"] == "error"
        assert "Failed to fetch stream data" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_sampling_unsupported(self, mock_deps, mock_ctx):
        """Test analyze_stream_with_llm when sampling is unsupported (Bug Regression)."""
        _, mock_search = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Hello"}]
        }

        # Simulate sampling error (e.g. client doesn't support it)
        mock_ctx.sample.side_effect = Exception("Client does not support sampling")

        result = await analyze_stream_with_llm("general", "summary", ctx=mock_ctx)

        assert result["status"] == "error"
        assert "LLM analysis failed" in result["error"]
        assert "Client does not support sampling" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_team_activity_with_llm(self, mock_deps, mock_ctx):
        """Test analyze_team_activity_with_llm."""
        _, mock_search = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work"}]
        }

        mock_ctx.sample.return_value = MagicMock(content=[TextContent(type="text", text="Team analysis")])

        result = await analyze_team_activity_with_llm(
            team_streams=["s1", "s2"],
            analysis_focus="productivity",
            ctx=mock_ctx
        )

        assert result["status"] == "success"
        assert result["analysis"] == "Team analysis"
        assert result["total_messages"] == 2 # 1 per stream * 2 streams

    @pytest.mark.asyncio
    async def test_intelligent_report_generator(self, mock_deps, mock_ctx):
        """Test intelligent_report_generator."""
        # This calls analyze_team_activity_with_llm internally
        # We can mock analyze_team_activity_with_llm, but since we are patching at module level,
        # we can just rely on the existing mocks for search and sample.

        _, mock_search = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work"}]
        }

        # sample called twice: once for analysis, once for report
        mock_ctx.sample.side_effect = [
            MagicMock(content=[TextContent(type="text", text="Analysis")]),
            MagicMock(content=[TextContent(type="text", text="Final Report")])
        ]

        result = await intelligent_report_generator(
            report_type="standup",
            target_streams=["s1"],
            ctx=mock_ctx
        )

        assert result["status"] == "success"
        assert result["report_content"] == "Final Report"
        assert mock_ctx.sample.call_count == 2
