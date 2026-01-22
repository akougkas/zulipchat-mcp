"""Tests for execute_chain in tools.commands using monkeypatched CommandChain and client."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


class DummyChain:
    def __init__(self, name, client):  # signature match
        self.name = name
        self.client = client
        self._summary = []
        self._context = SimpleNamespace(data={})

    def add_command(self, cmd):
        self._summary.append(type(cmd).__name__)

    def execute(self, initial_context):
        self._context.data.update(initial_context or {})
        return self._context

    def get_execution_summary(self):
        return self._summary


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass


class _DummyCmd:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _DummyConditional:
    def __init__(self, condition, true_command, false_command=None):
        self.condition = condition
        self.true_command = true_command
        self.false_command = false_command


@patch("zulipchat_mcp.tools.commands.CommandChain", DummyChain)
@patch("zulipchat_mcp.tools.commands.ZulipClientWrapper", DummyClient)
@patch("zulipchat_mcp.tools.commands.get_config_manager")
@patch("zulipchat_mcp.tools.commands.SearchMessagesCommand", _DummyCmd)
@patch("zulipchat_mcp.tools.commands.SendMessageCommand", _DummyCmd)
@patch("zulipchat_mcp.tools.commands.ConditionalActionCommand", _DummyConditional)
def test_execute_chain_smoke(*_patches) -> None:
    from zulipchat_mcp.tools.commands import execute_chain

    cmds = [
        {
            "type": "conditional_action",
            "params": {
                "condition": "False",
                "true_action": {"type": "search_messages"},
            },
        }
    ]
    out = execute_chain(cmds)
    assert out["status"] == "success"
    # Our DummyChain records class names of built commands (patched)
    assert out["summary"] == ["_DummyConditional"]
    assert isinstance(out["context"], dict)
