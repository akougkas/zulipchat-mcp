"""Analysis and reports describe the actual bounded excerpts in their prompts."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zulipchat_mcp.core.llm import LLMUnavailableError
from zulipchat_mcp.tools import ai_analytics as analytics
from zulipchat_mcp.tools import search


@pytest.mark.parametrize("unavailable", [False, True])
async def test_stream_sampling_counts_and_truncation(monkeypatch, unavailable):
    messages = [{"sender": "Alice", "content": "x" * 151} for _ in range(25)]
    messages[0]["content"] = "short"
    monkeypatch.setattr(analytics, "get_client", MagicMock())
    monkeypatch.setattr(
        search,
        "search_messages",
        AsyncMock(
            return_value={
                "status": "success",
                "messages": messages,
            }
        ),
    )
    generate = AsyncMock(return_value="analysis")
    if unavailable:
        generate.side_effect = LLMUnavailableError("unconfigured")
    monkeypatch.setattr(analytics, "generate", generate)
    result = await analytics.analyze_stream_with_llm("general", "summary")
    sample = result["sampling"]
    assert result["message_count"] == sample["fetched_message_count"] == 25
    assert sample["excerpt_count"] == sample["llm_input_excerpt_count"] == 20
    assert sample["omitted_message_count"] == 5
    assert sample["truncated_excerpt_count"] == 19
    assert sample["exhaustive"] is False
    prompt = generate.call_args.args[0]
    assert "showing 20 excerpts" in prompt
    assert "Alice: short\n" in prompt
    assert "x" * 150 + "..." in prompt
    if unavailable:
        assert result["data_summary"] in prompt


async def test_team_and_report_counts_preserve_sampling_provenance(monkeypatch):
    # Reuse records to ensure stream tagging never mutates upstream search data.
    messages = [{"sender": "Alice", "content": "x" * 101} for _ in range(7)]

    async def query(*, stream, **kwargs):
        return {"status": "success", "messages": [] if stream == "empty" else messages}

    monkeypatch.setattr(analytics, "get_client", MagicMock())
    monkeypatch.setattr(search, "search_messages", query)
    generate = AsyncMock(return_value="analysis")
    monkeypatch.setattr(analytics, "generate", generate)
    streams = ["empty", "one", "two", "three", "four", "five", "six"]
    result = await analytics.analyze_team_activity_with_llm(streams, "progress")
    sample = result["sampling"]
    assert result["total_messages"] == sample["fetched_message_count"] == 42
    assert result["streams_analyzed"] == 5
    assert sample["excerpt_count"] == sample["truncated_excerpt_count"] == 25
    assert sample["omitted_message_count"] == 17
    assert sample["included_streams"] == streams[1:6]
    assert sample["omitted_streams"] == ["empty", "six"]
    assert "#six" not in generate.call_args.args[0]
    assert all("stream" not in msg for msg in messages)

    report = await analytics.intelligent_report_generator("weekly", streams)
    assert report["data_analyzed"] == 25
    assert report["sampling"] == sample
    assert "25 message excerpts" in generate.call_args.args[0]
    assert "not exhaustive history" in generate.call_args.args[0]


async def test_custom_prompt_without_data_does_not_claim_excerpts_analyzed(monkeypatch):
    monkeypatch.setattr(analytics, "get_client", MagicMock())
    monkeypatch.setattr(
        search,
        "search_messages",
        AsyncMock(
            return_value={
                "status": "success",
                "messages": [{"sender": "Alice", "content": "sample"}],
            }
        ),
    )
    monkeypatch.setattr(analytics, "generate", AsyncMock(return_value="custom"))
    result = await analytics.analyze_team_activity_with_llm(
        ["general"], "summary", custom_prompt="Answer this unrelated question"
    )
    assert result["sampling"]["excerpt_count"] == 1
    assert result["sampling"]["llm_input_excerpt_count"] == 0
    assert result["streams_analyzed"] == 0
