"""Tests for tools.commands helpers to lift coverage.

Focuses on build_command, list_command_types, ConditionalActionCommand,
and WaitForResponseCommand error handling without exercising network paths.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from zulipchat_mcp.tools.commands import (
    ConditionalActionCommand as _BaseConditional,
)
from zulipchat_mcp.tools.commands import (
    WaitForResponseCommand as _BaseWait,
)
from zulipchat_mcp.tools.commands import (
    build_command,
    list_command_types,
)


def test_list_command_types_contains_expected() -> None:
    kinds = set(list_command_types())
    assert {
        "send_message",
        "wait_for_response",
        "search_messages",
        "conditional_action",
    } <= kinds


def test_build_command_errors() -> None:
    with pytest.raises(ValueError):
        build_command({})
    with pytest.raises(ValueError):
        build_command({"type": "unknown_kind"})


def test_build_command_errors_only_no_instantiation() -> None:
    # Keep to error paths to avoid instantiating abstract engine commands
    with pytest.raises(ValueError):
        build_command({})
    with pytest.raises(ValueError):
        build_command({"type": "unknown_kind"})


@dataclass
class DummyContext:
    data: dict

    def get(self, key, default=None):  # minimal context API used by commands
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class DummyCommand:
    def __init__(self, value: str) -> None:
        self.value = value
        self.called = False

    def execute(self, context, client):  # signature compatible
        self.called = True
        return {"status": self.value}


class ConditionalActionCommand(_BaseConditional):
    def _rollback_impl(self, context, client):  # pragma: no cover - not used
        return {"status": "rolled_back"}


def test_conditional_action_true_and_false_paths() -> None:
    ctx = DummyContext(data={"x": 2})
    tcmd, fcmd = DummyCommand("true"), DummyCommand("false")
    cond = ConditionalActionCommand("context['x'] > 1", tcmd, fcmd)
    out = cond.execute(ctx, client=None)
    assert out["status"] == "true" and tcmd.called and not fcmd.called

    ctx.data["x"] = 0
    tcmd.called = fcmd.called = False
    out = cond.execute(ctx, client=None)
    assert out["status"] == "false" and fcmd.called and not tcmd.called


class WaitForResponseCommand(_BaseWait):
    def _rollback_impl(self, context, client):  # pragma: no cover - not used
        return {"status": "rolled_back"}


def test_wait_for_response_requires_request_id() -> None:
    cmd = WaitForResponseCommand()
    ctx = DummyContext(data={})
    with pytest.raises(ValueError):
        cmd.execute(ctx, client=None)
