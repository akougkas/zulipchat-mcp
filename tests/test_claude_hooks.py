"""Tests for the Claude Code hook bridge."""

import os
import subprocess
from pathlib import Path

from src.zulipchat_mcp.claude_hooks import (
    _build_permission_prompt,
    _permission_decision_output,
    _persist_hook_env,
)


def test_build_permission_prompt_includes_tool_details() -> None:
    prompt = _build_permission_prompt(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
            "permission_suggestions": [{"type": "addRules"}],
        }
    )
    assert "Bash" in prompt
    assert "npm test" in prompt
    assert "Permission suggestions available: 1" in prompt


def test_permission_hook_waits_on_delivered_partial_request(monkeypatch):
    from unittest.mock import MagicMock

    from zulipchat_mcp import claude_hooks

    coordinator = MagicMock()
    coordinator.create_request.return_value = {
        "status": "partial",
        "delivered": True,
        "request_id": "req-123",
        "message_id": 10,
    }
    coordinator.db.update_agent_request.return_value = {"status": "success"}
    coordinator.db.get_agent_request.return_value = {
        "status": "answered",
        "response": "approve",
    }
    poll = MagicMock(return_value={"decision": "approve"})
    monkeypatch.setattr(claude_hooks, "_wait_for_topic_decision", poll)
    result = claude_hooks._handle_permission_request(
        coordinator,
        {
            "session_id": "s",
            "stream_name": "Agents-Channel",
            "topic_name": "t",
            "owner_email": "owner@example.com",
        },
        {},
        30,
    )
    assert result["hookSpecificOutput"]["decision"]["behavior"] == "allow"
    poll.assert_called_once()


def test_permission_decision_output_allow() -> None:
    output = _permission_decision_output("approve")
    decision = output["hookSpecificOutput"]["decision"]
    assert decision["behavior"] == "allow"


def test_permission_hook_pages_past_busy_topic_without_skipping_approval(monkeypatch):
    from unittest.mock import MagicMock

    from zulipchat_mcp import claude_hooks

    coordinator = MagicMock()
    coordinator.bot_client.get_messages_raw.side_effect = [
        {
            "result": "success",
            "found_newest": False,
            "messages": [
                {
                    "id": message_id,
                    "sender_email": "other@example.com",
                    "content": "busy",
                }
                for message_id in range(11, 111)
            ],
        },
        {
            "result": "success",
            "found_newest": True,
            "messages": [
                {
                    "id": 111,
                    "sender_email": "OWNER@example.com",
                    "content": "/approve req-123",
                }
            ],
        },
    ]
    sleep = MagicMock(side_effect=AssertionError("Backlog pages must not sleep"))
    monkeypatch.setattr(claude_hooks.time, "sleep", sleep)
    result = claude_hooks._wait_for_topic_decision(
        coordinator,
        stream_name="Agents-Channel",
        topic_name="t",
        owner_email="owner@example.com",
        request_id="req-123",
        min_message_id=10,
        timeout_seconds=30,
    )
    assert result == {
        "decision": "approve",
        "message_id": 111,
        "content": "/approve req-123",
    }
    calls = coordinator.bot_client.get_messages_raw.call_args_list
    assert [call.kwargs["anchor"] for call in calls] == ["10", "110"]
    assert all(call.kwargs["include_anchor"] is False for call in calls)
    sleep.assert_not_called()


def test_permission_decision_output_deny() -> None:
    output = _permission_decision_output("deny")
    decision = output["hookSpecificOutput"]["decision"]
    assert decision["behavior"] == "deny"
    assert decision["interrupt"] is False


def test_persist_hook_env(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "claude.env"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))

    _persist_hook_env(
        "agent-1",
        {
            "session_id": "sess-1",
            "stream_name": "Agents-Channel",
            "topic_name": "Agents/Session/project/claude/cc-123",
        },
        {"session_id": "claude-123"},
    )

    content = env_file.read_text()
    assert "ZULIPCHAT_AGENT_ID" in content
    assert "ZULIPCHAT_SESSION_ID" in content
    assert "ZULIPCHAT_CLAUDE_SESSION_ID" in content


def test_hook_environment_is_literal_shell_data(tmp_path, monkeypatch):
    env_file = tmp_path / "hook.env"
    marker = tmp_path / "executed"
    topic = f"$(touch {marker}) `touch {marker}` ' quoted \\\"\nnext line"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    _persist_hook_env(
        "agent",
        {"session_id": "session", "stream_name": "stream", "topic_name": topic},
        {},
    )
    result = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            'source "$1"; printf %s "$ZULIPCHAT_SESSION_TOPIC"',
            "bash",
            str(env_file),
        ],
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == topic
    assert not marker.exists()
