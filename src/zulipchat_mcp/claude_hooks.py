"""Claude Code hook bridge for Zulip-controlled agent sessions."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
from typing import Any

from .config import init_config_manager
from .core.agent_control import AgentCoordinator
from .core.agent_protocol import parse_control_message
from .utils.database import init_database
from .utils.database_manager import DatabaseManager
from .utils.logging import get_logger, setup_structured_logging

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bridge Claude Code hook events into Zulip session topics."
    )
    parser.add_argument("--zulip-config-file")
    parser.add_argument("--zulip-bot-config-file")
    parser.add_argument("--agent-name", default="claude")
    parser.add_argument("--agent-type", default="claude-code")
    parser.add_argument("--stream-name")
    parser.add_argument("--project-name")
    parser.add_argument(
        "--approval-timeout",
        type=int,
        default=int(os.getenv("ZULIPCHAT_APPROVAL_TIMEOUT", "900")),
    )
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def _load_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def _persist_hook_env(
    agent_id: str, session: dict[str, Any], payload: dict[str, Any]
) -> None:
    """Expose session metadata to future Bash commands inside Claude Code."""
    env_file = os.getenv("CLAUDE_ENV_FILE")
    if not env_file:
        return

    exports = {
        "ZULIPCHAT_AGENT_ID": agent_id,
        "ZULIPCHAT_SESSION_ID": str(session["session_id"]),
        "ZULIPCHAT_SESSION_STREAM": str(session["stream_name"]),
        "ZULIPCHAT_SESSION_TOPIC": str(session["topic_name"]),
        "ZULIPCHAT_CLAUDE_SESSION_ID": str(payload.get("session_id", "")),
    }
    with open(env_file, "a", encoding="utf-8") as handle:
        for key, value in exports.items():
            handle.write(f"export {key}={shlex.quote(value)}\n")


def _wait_for_topic_decision(
    coordinator: AgentCoordinator,
    *,
    stream_name: str,
    topic_name: str,
    owner_email: str,
    request_id: str,
    min_message_id: int,
    timeout_seconds: int,
) -> dict[str, Any] | None:
    """Poll the topic directly via Zulip REST until the owner replies."""
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        response = coordinator.bot_client.get_messages_raw(
            anchor="newest",
            num_before=50,
            num_after=0,
            narrow=[
                {"operator": "stream", "operand": stream_name},
                {"operator": "topic", "operand": topic_name},
            ],
            include_anchor=True,
            client_gravatar=False,
            apply_markdown=False,
        )
        if response.get("result") == "success":
            messages = sorted(
                response.get("messages", []), key=lambda item: item.get("id", 0)
            )
            for message in messages:
                message_id = int(message.get("id", 0))
                if message_id <= min_message_id:
                    continue
                if str(message.get("sender_email", "")).lower() != owner_email.lower():
                    continue
                parsed = parse_control_message(str(message.get("content", "")))
                if (
                    parsed.decision in {"approve", "deny"}
                    and parsed.request_id == request_id
                ):
                    return {
                        "decision": parsed.decision,
                        "message_id": message_id,
                        "content": str(message.get("content", "")),
                    }
        time.sleep(3)
    return None


def _build_permission_prompt(payload: dict[str, Any]) -> str:
    tool_name = payload.get("tool_name", "tool")
    tool_input = payload.get("tool_input", {})
    suggestion_count = len(payload.get("permission_suggestions", []))
    return (
        f"Claude Code requested permission for `{tool_name}`.\n\n"
        f"Input:\n```json\n{json.dumps(tool_input, indent=2, sort_keys=True)}\n```\n\n"
        f"Permission suggestions available: {suggestion_count}"
    )


def _permission_decision_output(decision: str) -> dict[str, Any]:
    if decision == "approve":
        behavior = "allow"
        body: dict[str, Any] = {"behavior": behavior}
    else:
        body = {
            "behavior": "deny",
            "message": "Denied by Zulip owner approval policy",
            "interrupt": False,
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": body,
        }
    }


def _announce_session_status(
    coordinator: AgentCoordinator,
    session_id: str,
    status: str,
    message: str,
) -> None:
    DatabaseManager().update_agent_session(session_id, status=status)
    coordinator.send_session_message(
        session_id=session_id,
        content=message,
        category=status,
    )


def _handle_permission_request(
    coordinator: AgentCoordinator,
    session: dict[str, Any],
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    request = coordinator.create_request(
        session_id=str(session["session_id"]),
        prompt=_build_permission_prompt(payload),
        request_type="approval",
        options=["approve", "deny"],
        context="This approval was triggered from Claude Code's PermissionRequest hook.",
        source_event="PermissionRequest",
        metadata=payload,
    )
    if request.get("status") != "success":
        return _permission_decision_output("deny")

    decision = _wait_for_topic_decision(
        coordinator,
        stream_name=str(session["stream_name"]),
        topic_name=str(session["topic_name"]),
        owner_email=str(session["owner_email"]),
        request_id=str(request["request_id"]),
        min_message_id=int(request.get("message_id", 0)),
        timeout_seconds=timeout_seconds,
    )

    if decision is None:
        DatabaseManager().update_agent_request(
            request["request_id"],
            status="timeout",
            response="timeout",
        )
        _announce_session_status(
            coordinator,
            str(session["session_id"]),
            "waiting",
            "Approval request timed out waiting for an owner response.",
        )
        return _permission_decision_output("deny")

    stored = coordinator.db.update_agent_request(
        request["request_id"],
        status="answered",
        response=decision["decision"],
    )
    persisted = coordinator.db.get_agent_request(request["request_id"])
    if (
        stored.get("status") != "success"
        or not persisted
        or persisted.get("status") != "answered"
    ):
        return _permission_decision_output("deny")
    return _permission_decision_output(str(persisted.get("response", "deny")))


def _handle_hook_event(
    coordinator: AgentCoordinator,
    session: dict[str, Any],
    payload: dict[str, Any],
    approval_timeout: int,
) -> dict[str, Any] | None:
    event_name = payload.get("hook_event_name")
    session_id = str(session["session_id"])

    if event_name == "PermissionRequest":
        return _handle_permission_request(
            coordinator,
            session,
            payload,
            timeout_seconds=approval_timeout,
        )

    if event_name == "SessionStart":
        source = payload.get("source", "startup")
        model = payload.get("model", "unknown")
        _announce_session_status(
            coordinator,
            session_id,
            "started",
            f"Claude Code session started via `{source}` on model `{model}`.",
        )
        return None

    if event_name == "PostToolUseFailure":
        tool_name = payload.get("tool_name", "tool")
        error = payload.get("error", "unknown error")
        _announce_session_status(
            coordinator,
            session_id,
            "blocked",
            f"`{tool_name}` failed: {error}",
        )
        return None

    if event_name == "StopFailure":
        error_type = payload.get("error_type", "unknown")
        _announce_session_status(
            coordinator,
            session_id,
            "failed",
            f"Claude Code stopped because of `{error_type}`.",
        )
        return None

    if event_name == "TaskCompleted":
        _announce_session_status(
            coordinator,
            session_id,
            "completed",
            "Claude Code reported task completion.",
        )
        return None

    if event_name == "SessionEnd":
        reason = payload.get("reason", "other")
        if reason not in {"resume", "clear"}:
            _announce_session_status(
                coordinator,
                session_id,
                "completed",
                f"Claude Code session ended with reason `{reason}`.",
            )
        else:
            DatabaseManager().update_agent_session(session_id, status="active")
        return None

    if event_name == "Notification":
        notification_type = payload.get("notification_type", "notification")
        if notification_type == "idle_prompt":
            _announce_session_status(
                coordinator,
                session_id,
                "waiting",
                str(payload.get("message", "Claude Code is waiting for attention.")),
            )
        return None

    return None


def main() -> None:
    args = _parse_args()
    setup_structured_logging("DEBUG" if args.debug else "INFO")

    payload = _load_payload()
    if not payload:
        logger.error("No hook payload received on stdin")
        sys.exit(1)

    config_manager = init_config_manager(
        config_file=args.zulip_config_file,
        bot_config_file=args.zulip_bot_config_file,
        debug=args.debug,
    )
    if not config_manager.validate_config():
        logger.error("Invalid Zulip configuration for Claude hook bridge")
        sys.exit(1)

    init_database()
    coordinator = AgentCoordinator()

    agent_result = coordinator.register_agent(
        agent_name=args.agent_name,
        agent_type=args.agent_type,
        stream_name=args.stream_name,
        metadata={"source": "claude-hook"},
    )
    if agent_result.get("status") != "success":
        logger.error("Failed to register agent profile: %s", agent_result)
        sys.exit(1)

    agent_id = agent_result["agent"]["agent_id"]
    session_result = coordinator.ensure_session(
        agent_id=agent_id,
        external_session_id=str(payload.get("session_id", "")) or None,
        project_name=args.project_name,
        project_dir=payload.get("cwd"),
        status="active",
        metadata={
            "hook_event_name": payload.get("hook_event_name"),
            "transcript_path": payload.get("transcript_path"),
        },
    )
    if session_result.get("status") != "success":
        logger.error("Failed to bind agent session: %s", session_result)
        sys.exit(1)

    session = session_result["session"]
    _persist_hook_env(agent_id, session, payload)

    result = _handle_hook_event(
        coordinator,
        session,
        payload,
        approval_timeout=args.approval_timeout,
    )
    if result is not None:
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
