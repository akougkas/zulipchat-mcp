"""Search and summary tools for ZulipChat MCP.

Optimized for latency with direct dict manipulation.
"""

from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.security import sanitize_input
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error

logger = get_logger(__name__)

# Maximum content size (50KB) - reasonable for most LLMs
MAX_CONTENT_SIZE = 50000

_client: ZulipClientWrapper | None = None


def _get_client() -> ZulipClientWrapper:
    """Get or create client instance."""
    global _client
    if _client is None:
        _client = ZulipClientWrapper(ConfigManager(), use_bot_identity=False)
    return _client


def _truncate_content(content: str) -> str:
    """Truncate content if it exceeds maximum size."""
    if len(content) > MAX_CONTENT_SIZE:
        return content[:MAX_CONTENT_SIZE] + "\n... [Content truncated]"
    return content


def search_messages(query: str, limit: int = 50) -> dict[str, Any]:
    """Search messages - optimized for latency."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "search_messages"}):
        with LogContext(logger, tool="search_messages", query=query[:50]):
            track_tool_call("search_messages")
            try:
                # Input validation
                if not query:
                    return {"status": "error", "error": "Query cannot be empty"}
                if not (1 <= limit <= 100):
                    return {
                        "status": "error",
                        "error": "limit must be between 1 and 100",
                    }

                client = _get_client()
                safe_query = sanitize_input(query)

                # Get raw response from Zulip
                response = client.search_messages(safe_query, num_results=limit)

                # Quick validation
                if response.get("result") != "success":
                    return {
                        "status": "error",
                        "error": response.get("msg", "Search failed"),
                    }

                # Extract only essential fields - no model creation
                messages = [
                    {
                        "id": msg["id"],
                        "sender": msg["sender_full_name"],
                        "email": msg["sender_email"],
                        "timestamp": msg["timestamp"],
                        "content": _truncate_content(msg["content"]),
                        "type": msg["type"],
                        "stream": msg.get("display_recipient"),
                        "topic": msg.get("subject"),
                    }
                    for msg in response.get("messages", [])
                ]

                return {
                    "status": "success",
                    "messages": messages,
                    "count": len(messages),
                    "query": safe_query,
                }

            except KeyError as e:
                track_tool_error("search_messages", "KeyError")
                logger.error(f"search_messages KeyError: {e}")
                return {"status": "error", "error": f"Missing expected field: {e}"}
            except Exception as e:
                track_tool_error("search_messages", type(e).__name__)
                logger.error(f"search_messages error: {type(e).__name__}: {str(e)}")
                return {
                    "status": "error",
                    "error": f"Failed to search messages: {str(e)}",
                }


def get_daily_summary(
    streams: list[str] | None = None, hours_back: int = 24
) -> dict[str, Any]:
    """Get daily summary of messages."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_daily_summary"}):
        with LogContext(logger, tool="get_daily_summary"):
            track_tool_call("get_daily_summary")
            try:
                # Input validation
                if not (1 <= hours_back <= 168):
                    return {
                        "status": "error",
                        "error": "hours_back must be between 1 and 168",
                    }

                client = _get_client()
                data = client.get_daily_summary(streams, hours_back)

                # Check for errors from client
                if "error" in data:
                    return {"status": "error", "error": data["error"]}

                return {"status": "success", "data": data}

            except KeyError as e:
                track_tool_error("get_daily_summary", "KeyError")
                logger.error(f"get_daily_summary KeyError: {e}")
                return {"status": "error", "error": f"Missing expected field: {e}"}
            except Exception as e:
                track_tool_error("get_daily_summary", type(e).__name__)
                logger.error(f"get_daily_summary error: {type(e).__name__}: {str(e)}")
                return {"status": "error", "error": f"Failed to get summary: {str(e)}"}


def register_search_tools(mcp: Any) -> None:
    """Register search tools on the given MCP instance."""
    mcp.tool(description="Search messages")(search_messages)
    mcp.tool(description="Daily summary")(get_daily_summary)
