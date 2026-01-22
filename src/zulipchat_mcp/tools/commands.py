"""Command chain tools for workflow automation.

Cleanup (v0.4):
- Replace legacy search import with a thin adaptor to `search_v25.advanced_search`.
  This keeps command chains working while aligning with the v0.4 tool surface.
"""

import asyncio
import json
from typing import Any

from ..config import get_config_manager
from ..core.client import ZulipClientWrapper
from ..core.commands.engine import (
    AddReactionCommand,
    Command,
    CommandChain,
    Condition,
    ConditionOperator,
    ExecutionContext,
    ExecutionStatus,
    GetMessagesCommand,
    ProcessDataCommand,
    SendMessageCommand,
)
from ..core.commands.workflows import ChainBuilder


def _get_command_format_example(cmd_type: str = "send_message") -> dict[str, Any]:
    """Get example format for command types.

    Returns:
        Dict showing correct command structure
    """
    examples = {
        "send_message": {
            "type": "send_message",
            "params": {
                "message_type_key": "msg_type",
                "to_key": "recipient",
                "content_key": "text",
                "topic_key": "subject",
            },
        },
        "search_messages": {
            "type": "search_messages",
            "params": {"query_key": "search_query"},
        },
        "wait_for_response": {
            "type": "wait_for_response",
            "params": {"request_id_key": "request_id"},
        },
    }
    return examples.get(cmd_type, examples["send_message"])


class WaitForResponseCommand(Command):
    """Wait for user response command."""

    def __init__(
        self,
        name: str = "wait_for_response",
        request_id_key: str = "request_id",
        **kwargs: Any,
    ):
        super().__init__(name, "Wait for user response", **kwargs)
        self.request_id_key = request_id_key

    def execute(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> dict[str, Any]:
        from ..tools.agents import wait_for_response

        request_id = context.get(self.request_id_key)
        if not request_id:
            raise ValueError("request_id required in context")
        result = wait_for_response(request_id)
        context.set("response", result.get("response"))
        return result

    def _rollback_impl(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> None:
        """No-op rollback for wait-for-response command."""
        return None


class SearchMessagesCommand(Command):
    """Search messages command."""

    def __init__(
        self,
        name: str = "search_messages",
        query_key: str = "search_query",
        **kwargs: Any,
    ):
        super().__init__(name, "Search messages", **kwargs)
        self.query_key = query_key

    def execute(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> dict[str, Any]:
        """Execute search via v0.4 advanced_search adaptor.

        Returns a legacy-shaped dict with a top-level "messages" list
        for backward compatibility with prior command chains.
        """
        from .search import advanced_search  # v0.4 tool

        query = context.get(self.query_key)
        if not query:
            raise ValueError("search_query required in context")

        async def _run() -> dict[str, Any]:
            res = await advanced_search(query, search_type=["messages"], limit=100)
            # Map v0.4 shape -> legacy shape expected by chains/tests
            msgs = res.get("results", {}).get("messages", {}).get("messages", [])
            return {"status": res.get("status", "success"), "messages": msgs}

        # Prefer asyncio.run, fallback to a dedicated loop if already inside one
        try:
            result = asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(_run())
            finally:
                loop.close()

        context.set("search_results", result.get("messages", []))
        return result

    def _rollback_impl(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> None:
        """No-op rollback for search command."""
        return None


class ConditionalActionCommand(Command):
    """Conditional execution based on a simple Python expression evaluated against context data."""

    def __init__(
        self,
        condition: str,
        true_command: Command,
        false_command: Command | None = None,
    ):
        super().__init__("conditional_action", "Conditional action")
        self.condition = condition
        self.true_command = true_command
        self.false_command = false_command

    def execute(self, context: ExecutionContext, client: ZulipClientWrapper) -> Any:
        # Evaluate condition against context data with no builtins
        try:
            condition_met = bool(
                eval(self.condition, {"__builtins__": {}}, {"context": context.data})
            )
        except Exception as e:
            raise ValueError(f"Invalid condition expression: {e}") from e

        if condition_met:
            return self.true_command.execute(context, client)
        elif self.false_command:
            return self.false_command.execute(context, client)
        return {"status": "skipped"}

    def _rollback_impl(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> None:
        """No-op rollback for conditional command."""
        return None


def build_command(cmd_dict: dict[str, Any]) -> Command:
    """Helper to build command from dict description."""
    if not cmd_dict or "type" not in cmd_dict:
        raise ValueError(
            f"Invalid command specification. Expected format:\n"
            f"{json.dumps(_get_command_format_example(), indent=2)}"
        )
    ctype = cmd_dict["type"]
    params = cmd_dict.get("params", {})

    if ctype == "send_message":
        return SendMessageCommand(**params)
    if ctype == "wait_for_response":
        return WaitForResponseCommand(**params)
    if ctype == "search_messages":
        return SearchMessagesCommand(**params)
    if ctype == "conditional_action":
        true_cmd = build_command(params.get("true_action", {}))
        false_cmd = (
            build_command(params.get("false_action", {}))
            if params.get("false_action")
            else None
        )
        return ConditionalActionCommand(
            params.get("condition", "False"), true_cmd, false_cmd
        )

    raise ValueError(
        f"Unknown command type: '{ctype}'\n"
        f"Supported types: send_message, search_messages, wait_for_response, conditional_action"
    )


def execute_chain(
    commands: list[dict[str, Any]], initial_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Execute command chain with supported command types.

    Args:
        commands: List of command dictionaries with type and params
        initial_context: Optional initial values for the execution context.
            Commands read values from context using key names, so populate
            this with values your commands will need.
            Example: {"search_query": "test", "message_type": "stream"}
    """
    chain = CommandChain("mcp_chain", client=ZulipClientWrapper(get_config_manager()))
    for cmd in commands:
        chain.add_command(build_command(cmd))
    context = chain.execute(initial_context=initial_context or {})
    return {
        "status": "success",
        "summary": chain.get_execution_summary(),
        "context": context.data,
    }


def list_command_types() -> list[str]:
    return [
        "send_message",
        "wait_for_response",
        "search_messages",
        "conditional_action",
    ]


def register_command_tools(mcp: Any) -> None:
    mcp.tool(
        description="Execute sophisticated command chains for workflow automation: supports sequential command execution with shared context, includes 4 command types (send_message, wait_for_response, search_messages, conditional_action), provides conditional branching with Python expressions, maintains execution context across commands, integrates with v0.4 tools (advanced_search adapter), handles async operations with fallback loops, and returns comprehensive execution summary with final context. Ideal for complex multi-step workflows like interactive conversations, data processing pipelines, and automated response systems."
    )(execute_chain)

    mcp.tool(
        description="List all available command types for workflow construction: returns supported command types array including send_message (Zulip messaging), wait_for_response (user input polling), search_messages (message query with v0.4 integration), and conditional_action (branching logic with Python expressions). Essential reference for building command chains with execute_chain. Each command type supports specific parameters and context integration for sophisticated workflow automation and multi-step operations."
    )(list_command_types)


# Export all symbols for compatibility wrapper
__all__ = [
    # Base classes
    "Command",
    "CommandChain",
    "ExecutionContext",
    "Condition",
    # Enums
    "ExecutionStatus",
    "ConditionOperator",
    # Command implementations
    "SendMessageCommand",
    "GetMessagesCommand",
    "AddReactionCommand",
    "ProcessDataCommand",
    "WaitForResponseCommand",
    "SearchMessagesCommand",
    "ConditionalActionCommand",
    # Builders and utilities
    "ChainBuilder",
    "execute_chain",
    "list_command_types",
    "build_command",
]
