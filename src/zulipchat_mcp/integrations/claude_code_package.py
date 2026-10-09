"""Claude Code package helpers for richer ZulipChat integration assets."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from .. import __version__
from ..skill_content import skill_files
from .package_writer import write_package


def _build_mcp_args(
    zulip_config_file: str,
    zulip_bot_config_file: str | None,
    *,
    extended_tools: bool,
) -> list[str]:
    args = ["zulipchat-mcp", "--zulip-config-file", zulip_config_file]
    if zulip_bot_config_file:
        args.extend(["--zulip-bot-config-file", zulip_bot_config_file])
    if extended_tools:
        args.append("--extended-tools")
    return args


def _build_hook_command(
    zulip_config_file: str,
    zulip_bot_config_file: str | None,
) -> str:
    command = [
        "uvx",
        "--from",
        "zulipchat-mcp",
        "zulipchat-mcp-hook",
        "--zulip-config-file",
        zulip_config_file,
    ]
    if zulip_bot_config_file:
        command.extend(["--zulip-bot-config-file", zulip_bot_config_file])
    return shlex.join(command)


def build_claude_hook_settings(
    zulip_config_file: str,
    zulip_bot_config_file: str | None,
) -> dict[str, Any]:
    """Build the Claude Code hook settings payload."""
    hook_command = _build_hook_command(zulip_config_file, zulip_bot_config_file)
    command_hook = {"type": "command", "command": hook_command}
    timeout_hook = {**command_hook, "timeout": 900}

    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume",
                    "hooks": [command_hook],
                }
            ],
            "PermissionRequest": [
                {
                    "matcher": ".*",
                    "hooks": [timeout_hook],
                }
            ],
            "PostToolUseFailure": [
                {
                    "matcher": ".*",
                    "hooks": [command_hook],
                }
            ],
            "Notification": [
                {
                    "matcher": "idle_prompt",
                    "hooks": [command_hook],
                }
            ],
            "StopFailure": [
                {
                    "matcher": ".*",
                    "hooks": [command_hook],
                }
            ],
            "TaskCompleted": [
                {
                    "hooks": [command_hook],
                }
            ],
            "SessionEnd": [
                {
                    "matcher": "other|prompt_input_exit|logout",
                    "hooks": [command_hook],
                }
            ],
        }
    }


def _control_plane_rules() -> str:
    return """
## Replies and reliable delivery

Questions use `/reply REQUEST_ID YOUR ANSWER`; approvals use `/approve REQUEST_ID`
or `/deny REQUEST_ID`. Call `wait_for_response(request_id=..., timeout_seconds=30)`
and retain the same request ID after a timeout. Do not post duplicate prompts.

Poll steering with `auto_ack=False` in the bound session. Handle each event, then
acknowledge its ID with `ack_event_ids` in the same session scope. Replayed events
must not repeat completed external actions. A delivered partial result includes
its message ID and `retry_safe=False`; inspect that result before retrying.
"""


def _skill_session_operator() -> str:
    return """---
name: zulipchat-session-operator
description: Run the current Claude Code session as a Zulip-controlled work session with topic-bound steering, approvals, and lifecycle updates.
disable-model-invocation: true
---

# Zulip session operator

Use this skill when the current Claude Code session is already bound to a Zulip topic
through `zulipchat-mcp-hook` and you want the rest of the work to respect that
control plane.

## Required setup

1. Read `ZULIPCHAT_SESSION_ID`, `ZULIPCHAT_SESSION_STREAM`, and
   `ZULIPCHAT_SESSION_TOPIC` from the shell before using any ZulipChat MCP tools.
2. If `ZULIPCHAT_SESSION_ID` is empty, stop and explain that the hook bridge has not
   initialized the session binding yet.

## Operating rules

1. Treat Zulip as the owner control plane for this session.
2. Poll `poll_agent_events(session_id=..., limit=20)` at the start of each work
   cycle, after each meaningful unit of work, and before going idle.
3. Interpret inbound events this way:
   - `steer`: treat the message as a high-priority owner instruction.
   - `command`: support `/status`, `/pause`, `/resume`, `/cancel`, and `/handoff`.
   - `approval_response`: only consume it when tied to a pending
     `request_user_input` approval flow.
4. Default notification policy is lifecycle-only. Use `agent_message` only for:
   `started`, `blocked`, `waiting`, `completed`, `failed`, or a targeted owner
   message that materially changes execution.
5. If you need a decision from the owner, call `request_user_input` instead of
   posting a freeform message.
6. Never spam the topic with token-by-token progress. One message per state
   transition is the expected behavior.
7. If you are running inside Claude's native loop mode, keep the same poll-work-post
   discipline for every loop turn.

## Command handling

- `/status`: send one concise status update covering current goal, next step, and any
  blockers.
- `/pause`: acknowledge, stop proactive work, and wait for a new owner message.
- `/resume`: acknowledge and continue from the current plan.
- `/cancel`: confirm the cancellation in the topic, stop work cleanly, and close the
  session if appropriate.
- `/handoff`: summarize state, remaining work, and risks for whoever takes over next.
- Any other slash command: reply once that it is not authorized or not supported by
  this session policy.
""" + _control_plane_rules()


def _skill_notifyme() -> str:
    return """---
name: zulipchat-notifyme
description: Send a deterministic message into the current Zulip-bound session topic.
disable-model-invocation: true
---

# Zulip notify me

Use this skill when you explicitly want to post to the bound Zulip topic outside the
default lifecycle hooks.

## Required setup

1. Read `ZULIPCHAT_SESSION_ID` from the shell.
2. If it is empty, stop and explain that there is no active Zulip-bound Claude
   session.

## Invocation contract

Interpret `$ARGUMENTS` as either:

- `<category> :: <message>`
- `<message>` for a plain `message` category

Supported categories:

- `message`
- `started`
- `blocked`
- `waiting`
- `completed`
- `failed`

## Execution

1. Parse the category and message.
2. Call `agent_message(session_id=..., category=..., content=...)`.
3. Keep the Zulip post concise and operational.
4. If the owner explicitly needs to reply with a choice, use
   `request_user_input(...)` instead.
""" + _control_plane_rules()


def _skill_loop() -> str:
    return """---
name: zulipchat-loop
description: Run the current Claude Code session as a continuous Zulip-aware work loop.
disable-model-invocation: true
---

# Zulip loop

Use this skill when you want the session to behave like a continuous autonomous worker
that still remains steerable from Zulip.

Treat `$ARGUMENTS` as the current mission or loop objective.

## Required setup

1. Read `ZULIPCHAT_SESSION_ID`, `ZULIPCHAT_SESSION_STREAM`, and
   `ZULIPCHAT_SESSION_TOPIC` from the shell.
2. If the session is not bound yet, stop and explain the missing hook setup.

## Loop contract

Each cycle should do exactly this:

1. Poll `poll_agent_events(session_id=..., limit=20)`.
2. Incorporate any owner steering or commands before doing more work.
3. Decide whether the lifecycle state changed. If it did, emit one lifecycle message.
4. Do one concrete unit of work toward the mission.
5. If blocked on owner input, call `request_user_input(...)` and wait.
6. Exit the loop when the mission is complete, the owner pauses or cancels the
   session, or the session binding is closed.

## `/loop` integration

If the current Claude Code build exposes the native `/loop` command, this skill's
instructions are the policy for each loop turn. If `/loop` is not available, follow
the same cycle in the current conversation instead of failing.
""" + _control_plane_rules()


def _agent_session_operator() -> str:
    return """---
name: zulip-session-operator
description: Owns the Zulip communication and owner-control plane for the current Claude Code session. Use proactively when work should stay synchronized with a Zulip topic.
skills:
  - zulipchat-session-operator
  - zulipchat-notifyme
  - zulipchat-loop
---

You are responsible for keeping the current Claude Code session aligned with its bound
Zulip topic.

Start by reading `ZULIPCHAT_SESSION_ID`, `ZULIPCHAT_SESSION_STREAM`, and
`ZULIPCHAT_SESSION_TOPIC` from the shell.

Then:

1. Use the preloaded skills as the operating procedure.
2. Keep outbound Zulip traffic minimal, deliberate, and lifecycle-oriented.
3. Escalate with `request_user_input` whenever the owner must choose between options.
4. Treat inbound topic steering as higher priority than speculative autonomous work.
"""


def _plugin_manifest() -> dict[str, Any]:
    return {
        "name": "zulipchat",
        "description": (
            "Connect Claude Code sessions to Zulip topics with lifecycle hooks, "
            "owner approvals, and bidirectional control."
        ),
        "version": __version__,
        "author": {"name": "Anthony Kougkas"},
        "homepage": "https://github.com/akougkas/zulipchat-mcp",
        "repository": "https://github.com/akougkas/zulipchat-mcp",
        "license": "MIT",
    }


def _plugin_mcp_config(
    zulip_config_file: str,
    zulip_bot_config_file: str | None,
    *,
    extended_tools: bool,
) -> dict[str, Any]:
    return {
        "mcpServers": {
            "zulipchat": {
                "type": "stdio",
                "command": "uvx",
                "args": _build_mcp_args(
                    zulip_config_file,
                    zulip_bot_config_file,
                    extended_tools=extended_tools,
                ),
            }
        }
    }


def standalone_package_files(
    zulip_config_file: str,
    zulip_bot_config_file: str | None,
) -> dict[str, str]:
    """Render standalone `.claude/` assets."""
    return {
        ".claude/settings.json": (
            json.dumps(
                build_claude_hook_settings(
                    zulip_config_file,
                    zulip_bot_config_file,
                ),
                indent=2,
            )
            + "\n"
        ),
        ".claude/skills/zulipchat-session-operator/SKILL.md": _skill_session_operator(),
        ".claude/skills/zulipchat-notifyme/SKILL.md": _skill_notifyme(),
        ".claude/skills/zulipchat-loop/SKILL.md": _skill_loop(),
        ".claude/agents/zulip-session-operator.md": _agent_session_operator(),
        ".claude/skills/zulipchat/SKILL.md": skill_files()["zulipchat/SKILL.md"],
    }


def plugin_package_files(
    zulip_config_file: str,
    zulip_bot_config_file: str | None,
    *,
    extended_tools: bool,
) -> dict[str, str]:
    """Render a Claude Code plugin package."""
    return {
        ".claude-plugin/plugin.json": json.dumps(_plugin_manifest(), indent=2) + "\n",
        ".mcp.json": (
            json.dumps(
                _plugin_mcp_config(
                    zulip_config_file,
                    zulip_bot_config_file,
                    extended_tools=extended_tools,
                ),
                indent=2,
            )
            + "\n"
        ),
        "hooks/hooks.json": (
            json.dumps(
                build_claude_hook_settings(
                    zulip_config_file,
                    zulip_bot_config_file,
                ),
                indent=2,
            )
            + "\n"
        ),
        "skills/zulipchat-session-operator/SKILL.md": _skill_session_operator(),
        "skills/zulipchat-notifyme/SKILL.md": _skill_notifyme(),
        "skills/zulipchat-loop/SKILL.md": _skill_loop(),
        "agents/zulip-session-operator.md": _agent_session_operator(),
        "skills/zulipchat/SKILL.md": skill_files()["zulipchat/SKILL.md"],
    }


def _owned_hook(hook: Any) -> bool:
    """Recognize only the exact companion entrypoint generated by this exporter."""
    if not isinstance(hook, dict) or hook.get("type") != "command":
        return False
    try:
        tokens = shlex.split(hook.get("command", ""))
    except (ValueError, TypeError):
        return False
    if tokens[:4] != ["uvx", "--from", "zulipchat-mcp", "zulipchat-mcp-hook"]:
        return False
    tail = tokens[4:]
    return (
        bool(tail)
        and len(tail) % 2 == 0
        and all(
            tail[index] in {"--zulip-config-file", "--zulip-bot-config-file"}
            and bool(tail[index + 1])
            for index in range(0, len(tail), 2)
        )
    )


def _merge_settings(current: str, rendered: str, *, force: bool = False) -> str:
    incoming = json.loads(rendered)
    payload: dict[str, Any] = {}
    payload = json.loads(current)
    if not isinstance(payload, dict):
        raise ValueError("Claude settings must contain a JSON object")

    hooks = payload.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Claude settings has a non-object `hooks` field")

    for event_name, groups in incoming.get("hooks", {}).items():
        existing = hooks.setdefault(event_name, [])
        if not isinstance(existing, list):
            raise ValueError(
                f"Claude settings has a non-array hook group for {event_name}"
            )
        for group in existing:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if (
                    isinstance(hook, dict)
                    and isinstance(hook.get("command"), str)
                    and "zulipchat-mcp-hook" in hook["command"]
                    and not _owned_hook(hook)
                ):
                    raise ValueError(
                        "Cannot safely identify ownership of an existing Zulip hook; "
                        "review and remove or merge that custom command before exporting"
                    )
        managed = [
            group
            for group in existing
            if isinstance(group, dict)
            and any(_owned_hook(hook) for hook in group.get("hooks", []))
        ]
        if any(group not in groups for group in managed):
            if not force:
                raise FileExistsError(
                    "Existing Zulip hooks differ; use --force to replace their credential binding"
                )
            preserved = []
            for group in existing:
                if group in managed:
                    other = [hook for hook in group["hooks"] if not _owned_hook(hook)]
                    if other:
                        preserved.append({**group, "hooks": other})
                else:
                    preserved.append(group)
            hooks[event_name] = existing = preserved
        for group in groups:
            if group not in existing:
                existing.append(group)

    return json.dumps(payload, indent=2) + "\n"


def export_claude_code_package(
    output_dir: str | Path,
    *,
    zulip_config_file: str,
    zulip_bot_config_file: str | None = None,
    mode: str = "standalone",
    extended_tools: bool = False,
    force: bool = False,
) -> list[dict[str, str]]:
    """Export a richer Claude Code package into a destination directory."""
    if mode == "standalone":
        files = standalone_package_files(
            zulip_config_file,
            zulip_bot_config_file,
        )
        from .agent_package import _merge_config

        files[".mcp.json"] = (
            json.dumps(
                _plugin_mcp_config(
                    zulip_config_file,
                    zulip_bot_config_file,
                    extended_tools=extended_tools,
                ),
                indent=2,
            )
            + "\n"
        )

        def merge_mcp(current: str, incoming: str) -> str:
            return _merge_config(
                current, incoming, path=".mcp.json", key="mcpServers", force=force
            )

        def merge_settings(current: str, incoming: str) -> str:
            return _merge_settings(current, incoming, force=force)

        return write_package(
            output_dir,
            files,
            force=force,
            mergers={".claude/settings.json": merge_settings, ".mcp.json": merge_mcp},
        )

    if mode == "plugin":
        files = plugin_package_files(
            zulip_config_file,
            zulip_bot_config_file,
            extended_tools=extended_tools,
        )
        return write_package(output_dir, files, force=force)

    raise ValueError(f"Unsupported Claude Code package mode: {mode}")
