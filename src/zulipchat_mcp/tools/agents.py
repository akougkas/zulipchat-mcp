"""Agent communication tools for ZulipChat MCP."""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import get_config_manager
from ..core.agent_tracker import AgentTracker
from ..core.client import ZulipClientWrapper
from ..utils.database_manager import DatabaseManager
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error
from ..utils.topics import project_from_path, topic_input

logger = get_logger(__name__)


_tracker: AgentTracker | None = None
_client: ZulipClientWrapper | None = None
_agent_stream: str | None = None  # Cached stream name


def _get_client_bot() -> ZulipClientWrapper:
    global _client
    if _client is None:
        _client = ZulipClientWrapper(get_config_manager(), use_bot_identity=True)
    return _client


def _get_agent_stream(client: ZulipClientWrapper | None = None) -> str:
    """Get the best available stream for agent communication.

    Checks in order: Agents-Channel, AI Bots, sandbox, then first public stream.
    Caches result for session consistency.
    """
    global _agent_stream
    if _agent_stream is not None:
        return _agent_stream

    if client is None:
        client = _get_client_bot()

    preferred_streams = ["Agents-Channel", "AI Bots", "sandbox", "general"]

    result = client.get_streams(include_public=True, include_subscribed=True)
    if result.get("result") != "success":
        _agent_stream = "general"  # Fallback if API fails
        return _agent_stream

    available = {s["name"]: s for s in result.get("streams", [])}

    # Check preferred streams in order
    for stream_name in preferred_streams:
        if stream_name in available:
            _agent_stream = stream_name
            return _agent_stream

    # Fallback: first public stream
    for stream in result.get("streams", []):
        if not stream.get("invite_only", True):
            _agent_stream = stream["name"]
            return _agent_stream

    _agent_stream = "general"  # Last resort
    return _agent_stream


def _get_tracker() -> AgentTracker:
    """Get the agent tracker with proper stream configuration."""
    global _tracker
    if _tracker is None:
        stream = _get_agent_stream()
        _tracker = AgentTracker(agent_stream=stream)
    return _tracker


def register_agent(agent_type: str = "claude-code") -> dict[str, Any]:
    """Register agent and create database records."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "register_agent"}):
        track_tool_call("register_agent")
        try:
            db = DatabaseManager()
            agent_id = str(uuid.uuid4())
            instance_id = str(uuid.uuid4())

            # Insert or update agent record
            db.execute(
                """
                INSERT OR REPLACE INTO agents (agent_id, agent_type, created_at, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (agent_id, agent_type, datetime.now(timezone.utc), "{}"),
            )

            # Insert agent instance
            db.execute(
                """
                INSERT INTO agent_instances
                (instance_id, agent_id, session_id, project_dir, host, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    instance_id,
                    agent_id,
                    str(uuid.uuid4())[:8],  # Short session ID
                    str(os.getcwd()),
                    os.getenv("HOSTNAME", "localhost"),
                    datetime.now(timezone.utc),
                ),
            )

            # Initialize AFK state (disabled by default)
            db.execute(
                """
                INSERT OR REPLACE INTO afk_state (id, is_afk, reason, updated_at)
                VALUES (1, ?, ?, ?)
                """,
                (False, "Agent ready for normal operations", datetime.now(timezone.utc)),
            )

            # Discover best available stream for agent communication
            client = _get_client_bot()
            discovered_stream = _get_agent_stream(client)

            # Update the tracker with discovered stream
            tracker = _get_tracker()
            tracker.set_agent_stream(discovered_stream)

            return {
                "status": "success",
                "agent_id": agent_id,
                "instance_id": instance_id,
                "agent_type": agent_type,
                "stream": discovered_stream,
                "afk_enabled": False,
            }

        except Exception as e:
            track_tool_error("register_agent", type(e).__name__)
            return {"status": "error", "error": str(e)}


def agent_message(
    content: str, require_response: bool = False, agent_type: str = "claude-code"
) -> dict[str, Any]:
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "agent_message"}):
        with LogContext(logger, tool="agent_message", agent_type=agent_type):
            track_tool_call("agent_message")
            try:
                afk_state = DatabaseManager().get_afk_state() or {}
                dev_override = os.getenv("ZULIP_DEV_NOTIFY", "0") in (
                    "1",
                    "true",
                    "True",
                )
                if not afk_state.get("is_afk") and not dev_override:
                    return {
                        "status": "skipped",
                        "reason": "AFK disabled; notifications gated",
                    }
                msg_info = _get_tracker().format_agent_message(
                    content, agent_type, require_response
                )
                if msg_info["status"] != "ready":
                    return msg_info

                client = _get_client_bot()
                result = client.send_message(
                    message_type="stream",
                    to=msg_info["stream"],
                    content=msg_info["content"],
                    topic=msg_info["topic"],
                )
                if result.get("result") == "success":
                    return {
                        "status": "success",
                        "message_id": result.get("id"),
                        "response_id": msg_info.get("response_id"),
                        "sent_via": "agent_message",
                    }
                return {"status": "error", "error": result.get("msg", "Failed to send")}
            except Exception as e:
                track_tool_error("agent_message", type(e).__name__)
                return {"status": "error", "error": str(e)}


def wait_for_response(request_id: str) -> dict[str, Any]:
    """Wait for user response - timeout-based polling via DatabaseManager."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "wait_for_response"}):
        track_tool_call("wait_for_response")
        try:
            db = DatabaseManager()
            timeout_seconds = 300
            start = time.time()

            while time.time() - start < timeout_seconds:
                result = db.get_input_request(request_id)

                if not result:
                    return {"status": "error", "error": "Request not found"}

                status = result.get("status")
                if status in ["answered", "cancelled"]:
                    responded_at = result.get("responded_at")
                    if isinstance(responded_at, datetime):
                        responded_at_val = responded_at.isoformat()
                    elif responded_at is None:
                        responded_at_val = None
                    else:
                        responded_at_val = str(responded_at)
                    return {
                        "status": "success",
                        "request_status": status,
                        "response": result.get("response"),
                        "responded_at": responded_at_val,
                    }

                time.sleep(1)

            # Timeout reached
            db.update_input_request(request_id, status="timeout")
            return {"status": "error", "error": "Response timeout"}

        except Exception as e:
            track_tool_error("wait_for_response", type(e).__name__)
            return {"status": "error", "error": str(e)}


def send_agent_status(
    agent_type: str, status: str, message: str = ""
) -> dict[str, Any]:
    """Send agent status update."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "send_agent_status"}):
        track_tool_call("send_agent_status")
        try:
            db = DatabaseManager()
            status_id = str(uuid.uuid4())
            db.create_agent_status(
                status_id=status_id,
                agent_type=agent_type,
                status=status,
                message=message,
            )
            return {"status": "success", "status_id": status_id}
        except Exception as e:
            track_tool_error("send_agent_status", type(e).__name__)
            return {"status": "error", "error": str(e)}


def request_user_input(
    agent_id: str,
    question: str,
    options: list[str] | None = None,
    context: str = "",
) -> dict[str, Any]:
    """Request input from user - smart routing via agent metadata."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "request_user_input"}):
        track_tool_call("request_user_input")
        try:
            afk_state = DatabaseManager().get_afk_state() or {}
            dev_override = os.getenv("ZULIP_DEV_NOTIFY", "0") in ("1", "true", "True")
            if not afk_state.get("is_afk") and not dev_override:
                return {
                    "status": "skipped",
                    "reason": "AFK disabled; input request gated",
                }
            db = DatabaseManager()

            # Get agent instance and metadata to determine routing
            agent_instance = db.get_agent_instance(agent_id)
            # Load agent metadata for richer routing if available
            agent_meta_row = db.query_one(
                "SELECT metadata FROM agents WHERE agent_id = ?",
                [agent_id],
            )
            agent_metadata = {}
            if agent_meta_row and agent_meta_row[0]:
                try:
                    agent_metadata = json.loads(agent_meta_row[0])
                except Exception:
                    agent_metadata = {}
            if not agent_instance and not agent_metadata:
                return {"status": "error", "error": "Agent not found"}

            # Short request ID for human-friendly replies
            request_id = str(uuid.uuid4())[:8]

            # Store request
            db.create_input_request(
                request_id=request_id,
                agent_id=agent_id,
                question=question,
                options=json.dumps(options) if options else None,
                context=context,
            )

            # Prepare message
            message = f"**Input Requested** (ID: {request_id})\n\n{question}"
            if options:
                message += "\n\nOptions:\n" + "\n".join(f"- {opt}" for opt in options)
            if context:
                message += f"\n\nContext: {context}"

            client = _get_client_bot()

            # Route based on available metadata
            user_email = agent_metadata.get("user_email") or (
                agent_instance.get("user_email") if agent_instance else None
            )
            stream_name = agent_metadata.get("stream_name")
            project_name = agent_metadata.get("project_name") or project_from_path(
                agent_instance.get("project_dir") if agent_instance else None
            )

            if user_email:
                result = client.send_message(
                    message_type="private",
                    to=[user_email],
                    content=message,
                )
            elif stream_name:
                result = client.send_message(
                    message_type="stream",
                    to=stream_name,
                    content=message,
                    topic=topic_input(project_name or "Project", request_id),
                )
            else:
                # Use dynamically discovered agent stream
                agent_stream = _get_agent_stream(client)
                result = client.send_message(
                    message_type="stream",
                    to=agent_stream,
                    content=message,
                    topic=topic_input(project_name or agent_id, request_id),
                )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "request_id": request_id,
                    "message": "Input request sent",
                }

            return {"status": "error", "error": result.get("msg", "Failed to send")}
        except Exception as e:
            track_tool_error("request_user_input", type(e).__name__)
            return {"status": "error", "error": str(e)}


def start_task(agent_id: str, name: str, description: str = "") -> dict[str, Any]:
    """Start a new task."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "start_task"}):
        track_tool_call("start_task")
        try:
            task_id = str(uuid.uuid4())
            db = DatabaseManager()

            # Insert task into database
            db.execute(
                """
                INSERT INTO tasks
                (task_id, agent_id, name, description, status, progress, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, agent_id, name, description, "started", 0, datetime.now(timezone.utc)),
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

            # Update task progress in database
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
    """Complete a task."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "complete_task"}):
        track_tool_call("complete_task")
        try:
            db = DatabaseManager()

            # Complete task in database
            db.execute(
                """
                UPDATE tasks
                SET status = ?, progress = ?, completed_at = ?, outputs = ?, metrics = ?
                WHERE task_id = ?
                """,
                ("completed", 100, datetime.now(timezone.utc), outputs, metrics, task_id),
            )

            return {"status": "success", "message": "Task completed"}
        except Exception as e:
            track_tool_error("complete_task", type(e).__name__)
            return {"status": "error", "error": str(e)}


def list_instances() -> dict[str, Any]:
    """List agent instances."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "list_instances"}):
        track_tool_call("list_instances")
        try:
            db = DatabaseManager()

            # Query agent instances from database
            instances = db.query(
                """
                SELECT ai.instance_id, ai.agent_id, a.agent_type, ai.session_id,
                       ai.project_dir, ai.host, ai.started_at
                FROM agent_instances ai
                JOIN agents a ON ai.agent_id = a.agent_id
                ORDER BY ai.started_at DESC
                """
            )

            instance_list = [
                {
                    "instance_id": row[0],
                    "agent_id": row[1],
                    "agent_type": row[2],
                    "session_id": row[3],
                    "project_dir": row[4],
                    "host": row[5],
                    "started_at": row[6].isoformat() if row[6] else None,
                }
                for row in instances
            ]

            return {"status": "success", "instances": instance_list}
        except Exception as e:
            track_tool_error("list_instances", type(e).__name__)
            return {"status": "error", "error": str(e)}


def enable_afk_mode(
    hours: int = 8, reason: str = "Away from computer"
) -> dict[str, Any]:
    """Enable AFK mode for automatic notifications when away."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "enable_afk_mode"}):
        track_tool_call("enable_afk_mode")
        try:
            DatabaseManager().set_afk_state(enabled=True, reason=reason, hours=hours)
            return {
                "status": "success",
                "message": f"AFK mode enabled for {hours} hours",
                "reason": reason,
            }
        except Exception as e:
            track_tool_error("enable_afk_mode", type(e).__name__)
            return {"status": "error", "error": str(e)}


def disable_afk_mode() -> dict[str, Any]:
    """Disable AFK mode - normal agent communication."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "disable_afk_mode"}):
        track_tool_call("disable_afk_mode")
        try:
            DatabaseManager().set_afk_state(enabled=False, reason="", hours=0)
            return {
                "status": "success",
                "message": "AFK mode disabled - normal operation",
            }
        except Exception as e:
            track_tool_error("disable_afk_mode", type(e).__name__)
            return {"status": "error", "error": str(e)}


def get_afk_status() -> dict[str, Any]:
    """Get current AFK mode status."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_afk_status"}):
        track_tool_call("get_afk_status")
        try:
            state = DatabaseManager().get_afk_state() or {}
            normalized = {
                "enabled": bool(state.get("is_afk")),
                "reason": state.get("reason"),
                "updated_at": state.get("updated_at"),
            }
            return {"status": "success", "afk_state": normalized}
        except Exception as e:
            track_tool_error("get_afk_status", type(e).__name__)
            return {"status": "error", "error": str(e)}


def poll_agent_events(
    limit: int = 50, topic_prefix: str | None = "Agents/Chat/"
) -> dict[str, Any]:
    """Poll unacknowledged chat events from Zulip.

    This allows an agent to receive user replies when AFK is enabled.
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "poll_agent_events"}):
        track_tool_call("poll_agent_events")
        try:
            db = DatabaseManager()
            events = db.get_unacked_events(limit=limit, topic_prefix=topic_prefix)
            ids = [e["id"] for e in events]
            if ids:
                db.ack_events(ids)
            return {"status": "success", "events": events, "count": len(events)}
        except Exception as e:
            track_tool_error("poll_agent_events", type(e).__name__)
            return {"status": "error", "error": str(e)}


def register_agent_tools(mcp: Any) -> None:
    mcp.tool(
        description="Register AI agent instance and create database records: generates unique agent_id and instance_id, stores agent metadata (type, session, project directory, hostname), initializes AFK state (disabled by default), validates Agents-Channel stream existence, and returns registration details. Essential first step for agent communication system. Creates persistent tracking across sessions with automatic UUID generation. Stores agent type (default: claude-code) and session information for multi-agent coordination."
    )(register_agent)

    mcp.tool(
        description="Send bot-authored messages to users via Agents-Channel stream using BOT identity: formats agent messages with metadata, respects AFK mode gating (sends only when AFK enabled or ZULIP_DEV_NOTIFY=1), supports response requirements with unique IDs, automatically routes to Agents-Channel stream with contextual topics, and returns message ID for tracking. Use for automated responses, status updates, and agent-initiated communication. Bypassed when AFK disabled to prevent notification spam. Alternative to messaging_v25.message for bot communications."
    )(agent_message)

    mcp.tool(
        description="Wait for user response with timeout-based polling: monitors database for user replies to input requests, supports 5-minute timeout with 1-second polling intervals, handles request status tracking (answered/cancelled/timeout), returns response content with timestamps, and automatically updates request status on timeout. Use with request_user_input for interactive workflows. Blocks execution until response received or timeout reached. Essential for synchronous user interaction patterns."
    )(wait_for_response)

    mcp.tool(
        description="Set and track agent status updates: creates timestamped status records in database, supports custom agent types and status messages, generates unique status IDs for tracking, and stores operational state information. Use for progress reporting, health checks, and workflow state communication. Enables status history tracking across agent sessions. Supports any status values (starting, working, completed, error, idle, etc.) with optional descriptive messages."
    )(send_agent_status)

    mcp.tool(
        description="Request interactive user input with intelligent routing: creates timestamped input requests with unique short IDs (8-char), supports multiple choice options and contextual information, respects AFK mode gating (only sends when enabled), routes via user email (DM), stream name, or fallback to Agents-Channel, stores requests in database for polling, and returns request ID for wait_for_response. Essential for agent-user interaction workflows. Automatically determines routing based on agent metadata and project context."
    )(request_user_input)

    mcp.tool(
        description="Initialize task tracking with database persistence: creates task records with unique IDs, stores task metadata (name, description, agent association), sets initial status and progress (0%), records start timestamps, and returns task_id for progress updates. Essential for long-running workflows and progress monitoring. Use with update_task_progress and complete_task for full task lifecycle management. Enables task history and analytics across agent sessions."
    )(start_task)

    mcp.tool(
        description="Update task progress with percentage and status tracking: modifies existing task records with new progress values (0-100%), supports optional status updates (working, blocked, error, etc.), updates database with current timestamp, and returns success confirmation. Use throughout task execution to provide progress visibility. Enables real-time progress monitoring and workflow state management. Supports any integer progress value and custom status descriptions."
    )(update_task_progress)

    mcp.tool(
        description="Finalize task completion with results tracking: marks task as completed (100% progress), records completion timestamp, stores task outputs and performance metrics as text, updates database status to 'completed', and returns success confirmation. Final step in task lifecycle. Enables task analytics, outcome tracking, and results retrieval. Stores arbitrary output data and metrics for post-completion analysis and reporting."
    )(complete_task)

    mcp.tool(
        description="Retrieve all agent instances with session details: queries database for complete agent instance information, includes agent metadata (type, ID, session ID), project directory and hostname tracking, start timestamps and duration calculations, joins with agent records for full context, and returns sorted list (newest first). Essential for multi-agent coordination, session management, and system monitoring. Enables agent discovery and cluster state visibility."
    )(list_instances)

    mcp.tool(
        description="Enable AFK (Away From Keyboard) mode for automatic notifications: activates agent communication system with configurable duration (default 8 hours), sets custom away reason message, stores AFK state in database with timestamps, enables agent_message and request_user_input tools to send notifications, and returns confirmation with duration. Use when away from computer to enable automatic agent communication. Overrides normal notification gating for urgent agent messages."
    )(enable_afk_mode)

    mcp.tool(
        description="Disable AFK mode and restore normal operation: deactivates automatic agent notification system, updates database AFK state to disabled, blocks agent_message and request_user_input notifications (unless ZULIP_DEV_NOTIFY=1), sets reason to normal operation mode, and returns confirmation. Use when returning to computer to prevent notification spam. Restores default behavior where agent tools respect user presence and don't send unsolicited messages."
    )(disable_afk_mode)

    mcp.tool(
        description="Query current AFK mode status with state details: retrieves AFK state from database, returns enabled/disabled status with reason message, includes last updated timestamp, normalizes boolean values for consistency, and provides current operational mode information. Use to check if automatic notifications are active before calling agent communication tools. Essential for understanding current agent behavior and notification policies."
    )(get_afk_status)

    mcp.tool(
        description="Poll unacknowledged chat events from Zulip with topic filtering: retrieves user messages and replies from Agents-Channel, filters by topic prefix (default: 'Agents/Chat/'), limits results (default 50 events), marks events as acknowledged in database, and returns event list with message content and metadata. Enables agent to receive user replies when in AFK mode. Essential for asynchronous agent-user communication and message queue processing."
    )(poll_agent_events)
