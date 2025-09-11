"""Command chain tools for workflow automation."""

from typing import Any, Dict

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.commands.engine import Command, CommandChain, SendMessageCommand


class WaitForResponseCommand(Command):
    """Wait for user response command."""

    def __init__(self, name: str = "wait_for_response", request_id_key: str = "request_id", **kwargs: Any):
        super().__init__(name, "Wait for user response", **kwargs)
        self.request_id_key = request_id_key

    def execute(self, context, client: ZulipClientWrapper):  # type: ignore[override]
        from ..tools.agents import wait_for_response

        request_id = context.get(self.request_id_key)
        if not request_id:
            raise ValueError("request_id required in context")
        result = wait_for_response(request_id)
        context.set("response", result.get("response"))
        return result


class SearchMessagesCommand(Command):
    """Search messages command."""

    def __init__(self, name: str = "search_messages", query_key: str = "search_query", **kwargs: Any):
        super().__init__(name, "Search messages", **kwargs)
        self.query_key = query_key

    def execute(self, context, client: ZulipClientWrapper):  # type: ignore[override]
        from ..tools.search import search_messages

        query = context.get(self.query_key)
        if not query:
            raise ValueError("search_query required in context")
        result = search_messages(query)
        context.set("search_results", result.get("messages", []))
        return result


class ConditionalActionCommand(Command):
    """Conditional execution based on a simple Python expression evaluated against context data."""

    def __init__(self, condition: str, true_command: Command, false_command: Command | None = None):
        super().__init__("conditional_action", "Conditional action")
        self.condition = condition
        self.true_command = true_command
        self.false_command = false_command

    def execute(self, context, client: ZulipClientWrapper):  # type: ignore[override]
        # Evaluate condition against context data with no builtins
        try:
            condition_met = bool(eval(self.condition, {"__builtins__": {}}, {"context": context.data}))
        except Exception as e:
            raise ValueError(f"Invalid condition expression: {e}")

        if condition_met:
            return self.true_command.execute(context, client)
        elif self.false_command:
            return self.false_command.execute(context, client)
        return {"status": "skipped"}


def build_command(cmd_dict: Dict[str, Any]) -> Command:
    """Helper to build command from dict description."""
    if not cmd_dict or "type" not in cmd_dict:
        raise ValueError("Invalid command specification")
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
        false_cmd = build_command(params.get("false_action", {})) if params.get("false_action") else None
        return ConditionalActionCommand(params.get("condition", "False"), true_cmd, false_cmd)

    raise ValueError(f"Unknown command type: {ctype}")


def execute_chain(commands: list[dict]) -> dict:
    """Execute command chain with supported command types."""
    chain = CommandChain("mcp_chain", client=ZulipClientWrapper(ConfigManager()))
    for cmd in commands:
        chain.add_command(build_command(cmd))
    context = chain.execute(initial_context={})
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
    mcp.tool(description="Execute a command chain")(execute_chain)
    mcp.tool(description="List available command types")(list_command_types)
