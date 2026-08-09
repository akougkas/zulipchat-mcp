"""Tests for tools/ai_analytics.py.

Analytics generation went through MCP sampling (ctx.sample) until the
2026-07-28 protocol removed it; the tools now call the server-side provider
in core/llm.py, which tests mock at the module boundary.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.core.llm import LLMResponseError, LLMUnavailableError
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
            patch("src.zulipchat_mcp.tools.ai_analytics.get_client") as mock_get_client,
            patch(
                "src.zulipchat_mcp.tools.search.search_messages", new_callable=AsyncMock
            ) as mock_search,
            patch(
                "src.zulipchat_mcp.tools.ai_analytics.generate", new_callable=AsyncMock
            ) as mock_generate,
        ):

            client = MagicMock()
            mock_get_client.return_value = client
            yield client, mock_search, mock_generate

    @pytest.mark.asyncio
    async def test_get_daily_summary(self, mock_deps):
        """Test get_daily_summary."""
        client, _, _ = mock_deps
        client.get_daily_summary.return_value = {"total": 10}

        result = await get_daily_summary(streams=["s1"], hours_back=12)

        assert result["status"] == "success"
        assert result["summary"]["total"] == 10
        client.get_daily_summary.assert_called_with(streams=["s1"], hours_back=12)

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_success(self, mock_deps):
        """Test analyze_stream_with_llm success."""
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Hello"}],
        }
        mock_generate.return_value = "Analysis result"

        result = await analyze_stream_with_llm(
            stream_name="general",
            analysis_type="summary",
        )

        assert result["status"] == "success"
        assert result["analysis"] == "Analysis result"
        mock_generate.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_search_failed(self, mock_deps):
        """Test analyze_stream_with_llm search failure."""
        _, mock_search, _ = mock_deps
        mock_search.return_value = {"status": "error"}

        result = await analyze_stream_with_llm("general", "summary")

        assert result["status"] == "error"
        assert "Failed to fetch stream data" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_provider_error(self, mock_deps):
        """Provider/network failures surface as tool errors."""
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Hello"}],
        }
        mock_generate.side_effect = Exception("Anthropic API unreachable")

        result = await analyze_stream_with_llm("general", "summary")

        assert result["status"] == "error"
        assert "LLM analysis failed" in result["error"]
        assert "Anthropic API unreachable" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_empty_response_is_error(self, mock_deps):
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Hello"}],
        }
        mock_generate.side_effect = LLMResponseError("no text content")

        result = await analyze_stream_with_llm("general", "summary")

        assert result["status"] == "error"
        assert "no text content" in result["error"]
        assert "llm_unavailable" not in result

    @pytest.mark.asyncio
    async def test_analyze_stream_with_llm_unavailable_degrades(self, mock_deps):
        """Without a configured provider, return structured data, not an error."""
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Hello"}],
        }
        mock_generate.side_effect = LLMUnavailableError("ANTHROPIC_API_KEY not set")

        result = await analyze_stream_with_llm("general", "summary")

        assert result["status"] == "success"
        assert result["analysis"] is None
        assert result["llm_unavailable"] is True
        assert "data_summary" in result

    @pytest.mark.asyncio
    async def test_analyze_team_activity_with_llm(self, mock_deps):
        """Test analyze_team_activity_with_llm."""
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work"}],
        }
        mock_generate.return_value = "Team analysis"

        result = await analyze_team_activity_with_llm(
            team_streams=["s1", "s2"],
            analysis_focus="productivity",
        )

        assert result["status"] == "success"
        assert result["analysis"] == "Team analysis"
        assert result["total_messages"] == 2  # 1 per stream * 2 streams

    @pytest.mark.asyncio
    async def test_analyze_team_empty_response_is_error(self, mock_deps):
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work"}],
        }
        mock_generate.side_effect = LLMResponseError("no text content")

        result = await analyze_team_activity_with_llm(["s1"], "productivity")

        assert result["status"] == "error"
        assert "no text content" in result["error"]
        assert "llm_unavailable" not in result

    @pytest.mark.asyncio
    async def test_intelligent_report_generator(self, mock_deps):
        """Test intelligent_report_generator."""
        # This calls analyze_team_activity_with_llm internally: generate is
        # invoked once for the analysis and once to format the report.
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work"}],
        }
        mock_generate.side_effect = ["Analysis", "Final Report"]

        result = await intelligent_report_generator(
            report_type="standup",
            target_streams=["s1"],
        )

        assert result["status"] == "success"
        assert result["report_content"] == "Final Report"
        assert mock_generate.call_count == 2

    @pytest.mark.asyncio
    async def test_intelligent_report_generator_llm_unavailable(self, mock_deps):
        """Report generator propagates graceful degradation from the analysis."""
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work"}],
        }
        mock_generate.side_effect = LLMUnavailableError("ANTHROPIC_API_KEY not set")

        result = await intelligent_report_generator(
            report_type="weekly",
            target_streams=["s1"],
        )

        assert result["status"] == "success"
        assert result["report_content"] is None
        assert result["llm_unavailable"] is True
        assert "team_activity" in result
        # The analysis call failed with LLMUnavailableError, so the report
        # generation call must not be attempted.
        assert mock_generate.call_count == 1

    @pytest.mark.asyncio
    async def test_report_empty_response_is_error(self, mock_deps):
        _, mock_search, mock_generate = mock_deps
        mock_search.return_value = {
            "status": "success",
            "messages": [{"sender": "Alice", "content": "Work"}],
        }
        mock_generate.side_effect = [
            "Analysis",
            LLMResponseError("no text content"),
        ]

        result = await intelligent_report_generator("weekly", ["s1"])

        assert result["status"] == "error"
        assert "no text content" in result["error"]
        assert "llm_unavailable" not in result
