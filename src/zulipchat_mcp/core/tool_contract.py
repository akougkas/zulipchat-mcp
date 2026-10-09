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
        "is_user_group_member",
        "advanced_search",
        "construct_narrow",
        "check_messages_match_narrow",
        "get_scheduled_messages",
        "list_sessions",
        "list_instances",
        "list_command_types",
    }
)


class ToolContractMiddleware(Middleware):
    """Keep discovery, enforced policy, and wire error state consistent.

    This policy restricts Zulip tool calls. It does not sandbox a coding host,
    authorize workspace execution, or restrict reads to a particular channel.
    """

    def __init__(self, *, read_only: bool = False, transport: str = "stdio"):
        self.read_only = read_only
        self.transport = transport

    async def on_list_tools(
        self, context: MiddlewareContext[Any], call_next: Any
    ) -> Any:
        tools = await call_next(context)
        if self.read_only:
            return [tool for tool in tools if tool.name in READ_ONLY_TOOLS]
        return tools

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: Any
    ) -> ToolResult:
        name = context.message.name
        if self.read_only and name not in READ_ONLY_TOOLS:
            data = {
                "status": "error",
                "error": "The read-only tool profile does not permit this tool",
                "error_code": "POLICY_DENIED",
                "retryable": False,
                "tool": name,
                "profile": "read-only",
            }
            return ToolResult(structured_content=data, is_error=True)

        result = await call_next(context)
        data = result.structured_content
        if not isinstance(data, dict):
            return result

        if name == "server_info" and data.get("status") == "success":
            mcp_context = context.fastmcp_context
            tools = await mcp_context.fastmcp.list_tools() if mcp_context else []
            data = {
                **data,
                "capabilities": {
                    "tool_profile": "read-only" if self.read_only else "full",
                    "transport": self.transport,
                    "enabled_tools": sorted(tool.name for tool in tools),
                    "enabled_tool_count": len(tools),
                    "identity_switching": not self.read_only
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
