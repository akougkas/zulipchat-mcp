"""Wire-level search coverage, UTC dates, truncation, and rate-limit fidelity."""

from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP

from zulipchat_mcp.core.tool_contract import ToolContractMiddleware
from zulipchat_mcp.tools import search


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_registered_search_reports_actual_sample_and_preserves_upstream_errors(
    mode, monkeypatch
):
    upstream = MagicMock()
    upstream.get_messages_raw.return_value = {
        "result": "success",
        "messages": [
            {
                "id": index,
                "timestamp": 1700000000 + index,
                "sender_full_name": "Owner",
                "sender_email": "owner@example.com",
                "type": "stream",
                "content": "x" * 1001,
            }
            for index in range(1, 4)
        ],
        "found_oldest": False,
        "found_newest": True,
        "_cache": {"hit": True, "age_seconds": 2, "snapshot_id": "synthetic"},
    }
    monkeypatch.setattr(search, "get_client", lambda: upstream)
    server = FastMCP("search-sample")
    server.tool(search.search_messages)
    server.add_middleware(ToolContractMiddleware())
    async with Client(server, mode=mode) as client:
        result = (
            await client.call_tool(
                "search_messages",
                {"limit": 1, "after_time": "2023-11-14T22:13:22Z", "fresh": True},
            )
        ).structured_content
        assert result["count"] == 1
        assert result["sample"]["truncated_excerpts"] == 1
        assert result["sample"]["completeness"] == "partial"
        assert result["sample"]["next_cursor"].startswith("3:")
        assert result["messages"][0]["id"] == 3
        assert result["messages"][0]["time"] == "2023-11-14T22:13+00:00"
        assert result["messages"][0]["truncated"] is True
        assert upstream.get_messages_raw.call_args.kwargs["use_cache"] is False
        assert upstream.get_messages_raw.call_args.kwargs["apply_markdown"] is False
        await client.call_tool(
            "search_messages", {"limit": 1, "content_format": "rendered_html"}
        )
        assert upstream.get_messages_raw.call_args.kwargs["apply_markdown"] is True
        upstream.get_messages_raw.return_value = {
            "result": "error",
            "code": "RATE_LIMIT_HIT",
            "msg": "Slow down",
            "retry-after": 28.7,
        }
        failed = await client.call_tool("search_messages", {}, raise_on_error=False)
        assert failed.is_error
        assert failed.structured_content["error"]["code"] == "RATE_LIMIT_HIT"
        assert failed.structured_content["error"]["retry_after_seconds"] == 28.7
        assert failed.structured_content["error"]["retryable"] is True
