"""Agent session tools for Zulip-controlled autonomous workflows."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import get_client, get_config_manager
from ..core.agent_control import AgentCoordinator
from ..core.cache import user_cache
from ..core.client import ZulipClientWrapper
from ..core.service_manager import ensure_listener
from ..utils.database_manager import DatabaseManager
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error
from .registration import optional_background_task

logger = get_logger(__name__)

_coordinator: AgentCoordinator | None = None


def _get_coordinator() -> AgentCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator()
    return _coordinator


def _get_client_bot() -> ZulipClientWrapper:
    return _get_coordinator().bot_client


def register_agent(
    agent_name: str = "claude",
    agent_type: str = "claude-code",
    owner_email: str | None = None,
    stream_name: str | None = None,
    topic_prefix: str = "Agents/Session",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register or update a stable agent profile."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "register_agent"}):
        track_tool_call("register_agent")
        try:
            result = _get_coordinator().register_agent(
                agent_name=agent_name,
                agent_type=agent_type,
                owner_email=owner_email,
                stream_name=stream_name,
                topic_prefix=topic_prefix,
                metadata=metadata,
            )
            if result.get("status") != "success":
                return result
            agent = result["agent"]
            return {
                "status": "success",
                "agent_id": agent["agent_id"],
                "agent_name": agent["agent_name"],
                "agent_type": agent["agent_type"],
                "owner_email": agent["owner_email"],
                "stream": agent["stream_name"],
                "topic_prefix": agent["topic_prefix"],
            }
        except Exception as e:
            track_tool_error("register_agent", type(e).__name__)
            return {"status": "error", "error": str(e)}


def ensure_agent_session(
    agent_id: str,
    external_session_id: str | None = None,
    topic_name: str | None = None,
    project_dir: str | None = None,
    project_name: str | None = None,
    status: str = "active",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or refresh the Zulip topic binding for an agent session."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "ensure_agent_session"}):
        track_tool_call("ensure_agent_session")
        try:
            result = _get_coordinator().ensure_session(
                agent_id=agent_id,
                external_session_id=external_session_id,
                topic_name=topic_name,
                project_dir=project_dir,
                project_name=project_name,
                status=status,
                metadata=metadata,
            )
            if result.get("status") != "success":
                return result
            session = result["session"]
            return {
                "status": "success",
                "session_id": session["session_id"],
                "agent_id": session["agent_id"],
                "external_session_id": session.get("external_session_id"),
                "stream_name": session["stream_name"],
                "topic_name": session["topic_name"],
                "owner_email": session["owner_email"],
                "project_name": session.get("project_name"),
                "status_name": session.get("status"),
                "created": result.get("created", False),
            }
        except Exception as e:
            track_tool_error("ensure_agent_session", type(e).__name__)
            return {"status": "error", "error": str(e)}


def agent_message(
    session_id: str,
    content: str,
    category: str = "message",
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a session-scoped message into the bound Zulip topic."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "agent_message"}):
        with LogContext(logger, tool="agent_message", session_id=session_id):
            track_tool_call("agent_message")
            try:
                return _get_coordinator().send_session_message(
                    session_id=session_id,
                    content=content,
                    category=category,
                    request_id=request_id,
                    metadata=metadata,
                )
            except Exception as e:
                track_tool_error("agent_message", type(e).__name__)
                return {"status": "error", "error": str(e)}


async def wait_for_response(
    request_id: str, timeout_seconds: int = 300
) -> dict[str, Any]:
    """Wait for a persisted agent request response."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "wait_for_response"}):
        track_tool_call("wait_for_response")
        try:
            await asyncio.to_thread(ensure_listener)
            return await _get_coordinator().wait_for_request_async(
                request_id, timeout_seconds=timeout_seconds
            )
        except Exception as e:
            track_tool_error("wait_for_response", type(e).__name__)
            return {"status": "error", "error": str(e)}


def send_agent_status(agent_id: str, status: str, message: str = "") -> dict[str, Any]:
    """Store an agent lifecycle status update."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "send_agent_status"}):
        track_tool_call("send_agent_status")
        try:
            profile = DatabaseManager().get_agent_profile(agent_id)
            if profile is None:
                return {"status": "error", "error": "Agent not found"}
            status_id = str(uuid.uuid4())
            DatabaseManager().create_agent_status(
                status_id=status_id,
                agent_type=str(profile["agent_type"]),
                status=status,
                message=message,
            )
            return {"status": "success", "status_id": status_id, "agent_id": agent_id}
        except Exception as e:
            track_tool_error("send_agent_status", type(e).__name__)
            return {"status": "error", "error": str(e)}


def request_user_input(
    session_id: str,
    question: str,
    options: list[str] | None = None,
    context: str = "",
    request_type: str = "question",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a session-bound question or approval request to Zulip."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "request_user_input"}):
        track_tool_call("request_user_input")
        try:
            return _get_coordinator().create_request(
                session_id=session_id,
                prompt=question,
                request_type=request_type,
                options=options,
                context=context,
                source_event="mcp-tool",
                metadata=metadata,
            )
        except Exception as e:
            track_tool_error("request_user_input", type(e).__name__)
            return {"status": "error", "error": str(e)}


def start_task(agent_id: str, name: str, description: str = "") -> dict[str, Any]:
    """Start a tracked task for an agent."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "start_task"}):
        track_tool_call("start_task")
        try:
            task_id = str(uuid.uuid4())
            db = DatabaseManager()
            db.execute(
                """
                INSERT INTO tasks
                (task_id, agent_id, name, description, status, progress, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    agent_id,
                    name,
                    description,
                    "started",
                    0,
                    datetime.now(timezone.utc),
                ),
            )
            return {"status": "success", "task_id": task_id}
        except Exception as e:
            track_tool_error("start_task", type(e).__name__)
            return {"status": "error", "error": str(e)}


def update_task_progress(
    task_id: str, progress: int, status: str = ""
) -> dict[str, Any]:
    """Update task progress."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "update_task_progress"}):
        track_tool_call("update_task_progress")
        try:
            db = DatabaseManager()
            update_sql = "UPDATE tasks SET progress = ?"
            params: list[Any] = [progress]
            if status:
                update_sql += ", status = ?"
                params.append(status)
            update_sql += " WHERE task_id = ?"
            params.append(task_id)
            db.execute(update_sql, params)
            return {"status": "success", "message": "Progress updated"}
        except Exception as e:
            track_tool_error("update_task_progress", type(e).__name__)
            return {"status": "error", "error": str(e)}


def complete_task(task_id: str, outputs: str = "", metrics: str = "") -> dict[str, Any]:
    """Complete a tracked task."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "complete_task"}):
        track_tool_call("complete_task")
        try:
            db = DatabaseManager()
            db.execute(
                """
                UPDATE tasks
                SET status = ?, progress = ?, completed_at = ?, outputs = ?, metrics = ?
                WHERE task_id = ?
                """,
                (
                    "completed",
                    100,
                    datetime.now(timezone.utc),
                    outputs,
                    metrics,
                    task_id,
                ),
            )
            return {"status": "success", "message": "Task completed"}
        except Exception as e:
            track_tool_error("complete_task", type(e).__name__)
            return {"status": "error", "error": str(e)}


def list_sessions(
    agent_id: str | None = None, include_closed: bool = True
) -> dict[str, Any]:
    """List known agent sessions."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "list_sessions"}):
        track_tool_call("list_sessions")
        try:
            sessions = DatabaseManager().list_agent_sessions(
                agent_id=agent_id, include_closed=include_closed
            )
            for session in sessions:
                for key in ("created_at", "updated_at", "ended_at"):
                    if isinstance(session.get(key), datetime):
                        session[key] = session[key].isoformat()
            return {"status": "success", "sessions": sessions}
        except Exception as e:
            track_tool_error("list_sessions", type(e).__name__)
            return {"status": "error", "error": str(e)}


def list_instances() -> dict[str, Any]:
    """Compatibility wrapper returning agent sessions under the old name."""
    result = list_sessions()
    if result.get("status") != "success":
        return result
    return {"status": "success", "instances": result["sessions"]}


def close_agent_session(
    session_id: str, status: str = "completed", summary: str = ""
) -> dict[str, Any]:
    """Close a session binding and optionally announce the result."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "close_agent_session"}):
        track_tool_call("close_agent_session")
        try:
            db = DatabaseManager()
            session = db.get_agent_session(session_id)
            if session is None:
                return {"status": "error", "error": "Session not found"}
            db.update_agent_session(session_id, status=status)
            if summary:
                _get_coordinator().send_session_message(
                    session_id=session_id,
                    content=summary,
                    category=status if status in {"completed", "failed"} else "message",
                )
            return {
                "status": "success",
                "session_id": session_id,
                "status_name": status,
            }
        except Exception as e:
            track_tool_error("close_agent_session", type(e).__name__)
            return {"status": "error", "error": str(e)}


def poll_agent_events(
    limit: int = 50,
    agent_id: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    """Poll unacknowledged inbound session events."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "poll_agent_events"}):
        track_tool_call("poll_agent_events")
        try:
            ensure_listener()
            db = DatabaseManager()
            events = db.get_unacked_session_events(
                limit=limit,
                agent_id=agent_id,
                session_id=session_id,
                event_type=event_type,
            )
            ids = [str(event["id"]) for event in events]
            if ids:
                db.ack_session_events(ids)
            return {"status": "success", "events": events, "count": len(events)}
        except Exception as e:
            track_tool_error("poll_agent_events", type(e).__name__)
            return {"status": "error", "error": str(e)}


async def teleport_chat(
    to: str,
    message: str,
    wait_for_reply: bool = False,
    reply_timeout: int = 300,
    channel: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Send a message to a Zulip user or channel with identity-aware routing."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "teleport_chat"}):
        track_tool_call("teleport_chat")
        try:
            config = get_config_manager()
            target = to.strip()

            is_channel = target.startswith("#") or channel is not None
            resolved_channel = channel or (
                target.lstrip("#") if target.startswith("#") else None
            )

            if is_channel and resolved_channel:
                client = get_client()
                result = await asyncio.to_thread(
                    client.send_message,
                    message_type="stream",
                    to=resolved_channel,
                    content=message,
                    topic=topic or "general",
                )
                identity_used = "user"
                target_email = None
            else:
                target_email = target
                if "@" not in target:
                    resolution = user_cache.resolve_user(target)
                    if not resolution.get("email"):
                        from .users import get_users as _get_users

                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = None
                        if loop and loop.is_running():
                            result = await _get_users()
                            if result.get("status") == "success":
                                user_cache.set_users(result.get("users", []))
                        else:
                            result = asyncio.run(_get_users())
                            if result.get("status") == "success":
                                user_cache.set_users(result.get("users", []))
                        resolution = user_cache.resolve_user(target)
                    if not resolution.get("email"):
                        return {
                            "status": "error",
                            "error": f"Could not resolve user: {target}",
                        }
                    target_email = str(resolution["email"])

                user_client = get_client()
                _ = user_client.client
                user_email = user_client.current_email
                is_self_dm = user_cache.is_same_user(target_email, user_email or "")

                if is_self_dm and config.has_bot_credentials():
                    client = _get_client_bot()
                    identity_used = "bot"
                else:
                    client = user_client
                    identity_used = "user"

                result = await asyncio.to_thread(
                    client.send_message,
                    message_type="private",
                    to=[target_email],
                    content=message,
                )

            if result.get("result") != "success":
                return {"status": "error", "error": result.get("msg", "Failed to send")}

            response: dict[str, Any] = {
                "status": "success",
                "message_id": result.get("id"),
                "identity": identity_used,
                "target": resolved_channel if is_channel else target_email,
            }

            if wait_for_reply:
                await asyncio.to_thread(ensure_listener)
                db = DatabaseManager()
                start = time.time()
                while time.time() - start < reply_timeout:
                    events = await asyncio.to_thread(db.get_unacked_events, limit=10)
                    for event in events:
                        sender = event.get("sender_email", "")
                        if is_channel:
                            if event.get("topic") == (topic or "general"):
                                await asyncio.to_thread(db.ack_events, [event["id"]])
                                response["reply"] = event.get("content")
                                response["reply_from"] = sender
                                return response
                        elif sender == target_email:
                            await asyncio.to_thread(db.ack_events, [event["id"]])
                            response["reply"] = event.get("content")
                            response["reply_from"] = sender
                            return response
                    await asyncio.sleep(2)
                response["reply"] = None
                response["reply_timeout"] = True

            return response
        except Exception as e:
            track_tool_error("teleport_chat", type(e).__name__)
            return {"status": "error", "error": str(e)}


def manage_task(
    action: str,
    agent_id: str | None = None,
    task_id: str | None = None,
    name: str = "",
    description: str = "",
    progress: int = 0,
    status: str = "",
    outputs: str = "",
    metrics: str = "",
) -> dict[str, Any]:
    """Dispatch task lifecycle actions."""
    if action == "start":
        if not agent_id:
            return {"status": "error", "error": "agent_id required to start a task"}
        return start_task(agent_id, name, description)
    if action == "update":
        if not task_id:
            return {"status": "error", "error": "task_id required to update a task"}
        return update_task_progress(task_id, progress, status)
    if action == "complete":
        if not task_id:
            return {"status": "error", "error": "task_id required to complete a task"}
        return complete_task(task_id, outputs, metrics)
    return {"status": "error", "error": f"Unknown action: {action}"}


def register_agent_tools(mcp: Any) -> None:
    """Compatibility registrar for direct agent-tool registration."""
    interactive_task = optional_background_task(poll_seconds=2)
    for tool in (
        register_agent,
        ensure_agent_session,
        agent_message,
        request_user_input,
        send_agent_status,
        start_task,
        update_task_progress,
        complete_task,
        list_sessions,
        list_instances,
        close_agent_session,
        poll_agent_events,
    ):
        mcp.tool()(tool)
    mcp.tool(task=interactive_task)(teleport_chat)
    mcp.tool(task=interactive_task)(wait_for_response)


__all__ = [
    "teleport_chat",
    "register_agent",
    "ensure_agent_session",
    "agent_message",
    "request_user_input",
    "wait_for_response",
    "send_agent_status",
    "start_task",
    "update_task_progress",
    "complete_task",
    "list_sessions",
    "list_instances",
    "close_agent_session",
    "poll_agent_events",
    "manage_task",
    "register_agent_tools",
]
