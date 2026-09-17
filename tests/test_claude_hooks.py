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


def test_permission_decision_output_allow() -> None:
    output = _permission_decision_output("approve")
    decision = output["hookSpecificOutput"]["decision"]
    assert decision["behavior"] == "allow"


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
