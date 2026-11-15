"""Expose the effective tool policy and truthful MCP execution outcomes."""

from __future__ import annotations

from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

# Mixed-operation tools are deliberately excluded: their names alone cannot
# establish that a call is read-only. Listener tools can register remote queues.
READ_ONLY_TOOLS = frozenset(
    {
        "server_info",
        "get_message",
        "search_messages",
        "get_streams",
        "get_stream_info",
        "get_stream_topics",
        "resolve_user",
        "get_users",
        "get_own_user",
        "get_user",
        "get_user_status",
        "get_user_presence",
        "get_presence",
        "get_user_groups",
        "get_user_group_members",
        "check_messages_match_narrow",
        "get_scheduled_messages",
        "get_drafts",
        "get_read_receipts",
        "get_message_history",
        "get_daily_summary",
        "list_sessions",
    }
)

# Surface for a session the owner invokes from Zulip: it listens, reads with the
# bot's own visibility, and answers only in the conversation that asked.
BOT_TOOLS = frozenset(
    {
        "wait_for_mentions",
        "reply",
        "server_info",
        "get_message",
        "search_messages",
        "get_streams",
        "get_stream_topics",
        "resolve_user",
        "get_users",
    }
)

PROFILE_TOOLS: dict[str, frozenset[str] | None] = {
    "full": None,
    "read-only": READ_ONLY_TOOLS,
    "bot": BOT_TOOLS,
}


class ToolContractMiddleware(Middleware):
    """Keep discovery, enforced policy, and wire error state consistent.

    This policy restricts Zulip tool calls. It does not sandbox a coding host,
    authorize workspace execution, or restrict reads to a particular channel.
    """

    def __init__(
        self,
        *,
        read_only: bool = False,
        transport: str = "stdio",
        profile: str | None = None,
    ):
        self.profile = profile or ("read-only" if read_only else "full")
        self.allowed = PROFILE_TOOLS[self.profile]
        self.read_only = self.profile == "read-only"
        self.transport = transport

    async def on_list_tools(
        self, context: MiddlewareContext[Any], call_next: Any
    ) -> Any:
        tools = await call_next(context)
        if self.allowed is not None:
            return [tool for tool in tools if tool.name in self.allowed]
        return tools

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: Any
    ) -> Any:
        name = context.message.name
        if self.allowed is not None and name not in self.allowed:
            denied = {
                "status": "error",
                "error": f"The {self.profile} tool profile does not permit this tool",
                "error_code": "POLICY_DENIED",
                "retryable": False,
                "tool": name,
                "profile": self.profile,
            }
            return ToolResult(structured_content=denied, is_error=True)

        result = await call_next(context)
        # A task-augmented call returns a task handle, not a tool result.
        if not isinstance(result, ToolResult):
            return result
        data = result.structured_content
        if not isinstance(data, dict):
            return result

        if name == "server_info" and data.get("status") == "success":
            mcp_context = context.fastmcp_context
            tools = await mcp_context.fastmcp.list_tools() if mcp_context else []
            data = {
                **data,
                "capabilities": {
                    "tool_profile": self.profile,
                    "transport": self.transport,
                    "enabled_tools": sorted(tool.name for tool in tools),
                    "enabled_tool_count": len(tools),
                    "identity_switching": self.profile == "full"
                    and self.transport == "stdio",
                    "scope": "configured Zulip account",
                },
            }
            return ToolResult(
                structured_content=data, meta=result.meta, is_error=result.is_error
            )

        # Preserve structured details, backend codes and partial delivery data.
        # A timeout, pending request or unavailable optional LLM is not an error.
        if data.get("status") == "error" and not result.is_error:
            return ToolResult(structured_content=data, meta=result.meta, is_error=True)
        return result
