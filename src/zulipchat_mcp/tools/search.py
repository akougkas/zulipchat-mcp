"""Search and summary tools for ZulipChat MCP."""

from typing import Any

from ..core.client import ZulipClientWrapper
from ..config import ConfigManager
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error
from ..core.security import sanitize_input

logger = get_logger(__name__)


_client: ZulipClientWrapper | None = None


def _get_client() -> ZulipClientWrapper:
    global _client
    if _client is None:
        _client = ZulipClientWrapper(ConfigManager(), use_bot_identity=False)
    return _client


def search_messages(query: str, limit: int = 50) -> list[dict[str, Any]]:
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "search_messages"}):
        with LogContext(logger, tool="search_messages", query=query[:50]):
            track_tool_call("search_messages")
            try:
                if not query:
                    return [{"error": "Query cannot be empty"}]
                if not (1 <= limit <= 100):
                    return [{"error": "limit must be between 1 and 100"}]

                client = _get_client()
                safe_query = sanitize_input(query)
                messages = client.search_messages(safe_query, num_results=limit)
                return [
                    {
                        "id": m.id,
                        "sender": m.sender_full_name,
                        "email": m.sender_email,
                        "timestamp": m.timestamp,
                        "content": m.content,
                        "type": m.type,
                        "stream": m.stream_name,
                        "topic": m.subject,
                    }
                    for m in messages
                ]
            except Exception as e:
                track_tool_error("search_messages", type(e).__name__)
                return [{"error": "An unexpected error occurred"}]


def get_daily_summary(streams: list[str] | None = None, hours_back: int = 24) -> dict[str, Any]:
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_daily_summary"}):
        with LogContext(logger, tool="get_daily_summary"):
            track_tool_call("get_daily_summary")
            try:
                if not (1 <= hours_back <= 168):
                    return {"status": "error", "error": "hours_back must be between 1 and 168"}
                client = _get_client()
                data = client.get_daily_summary(streams, hours_back)
                return {"status": "success", "data": data}
            except Exception as e:
                track_tool_error("get_daily_summary", type(e).__name__)
                return {"status": "error", "error": "An unexpected error occurred"}


def register_search_tools(mcp: Any) -> None:
    mcp.tool(description="Search messages")(search_messages)
    mcp.tool(description="Daily summary")(get_daily_summary)
