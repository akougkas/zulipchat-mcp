"""Command chain tools registrar for ZulipChat MCP."""

from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.commands.engine import CommandChain, SendMessageCommand


def execute_chain(commands: list[dict]) -> dict:
    chain = CommandChain("mcp_chain", client=ZulipClientWrapper(ConfigManager()))
    for cmd in commands:
        if cmd.get("type") == "send_message":
            params = cmd.get("params", {})
            chain.add_command(
                SendMessageCommand(
                    message_type_key=params.get("message_type_key", "message_type"),
                    to_key=params.get("to_key", "to"),
                    content_key=params.get("content_key", "content"),
                    topic_key=params.get("topic_key", "topic"),
                )
            )
        # Add more command mappings as needed
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
