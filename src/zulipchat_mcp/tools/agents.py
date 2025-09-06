"""Agent communication tools for ZulipChat MCP."""

import os
import time
import uuid
from datetime import datetime
from typing import Any

from ..config import ConfigManager
from ..core.agent_tracker import AgentTracker
from ..core.client import ZulipClientWrapper
from ..utils.database import get_database
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error

logger = get_logger(__name__)


_tracker = AgentTracker()
_client: ZulipClientWrapper | None = None


def _get_client_bot() -> ZulipClientWrapper:
    global _client
    if _client is None:
        _client = ZulipClientWrapper(ConfigManager(), use_bot_identity=True)
    return _client


def register_agent(agent_type: str = "claude-code") -> dict[str, Any]:
    """Register agent and create database records."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "register_agent"}):
        track_tool_call("register_agent")
        try:
            db = get_database()
            agent_id = str(uuid.uuid4())
            instance_id = str(uuid.uuid4())

            # Insert or update agent record
            db.execute(
                """
                INSERT OR REPLACE INTO agents (agent_id, agent_type, created_at, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (agent_id, agent_type, datetime.utcnow(), "{}"),
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
                    "localhost",
                    datetime.utcnow(),
                ),
            )

            # Initialize AFK state
            db.execute(
                """
                INSERT OR REPLACE INTO afk_state (id, is_afk, reason, updated_at)
                VALUES (1, ?, ?, ?)
                """,
                (True, "Agent starting up", datetime.utcnow()),
            )

            # Check if Agents-Channel stream exists
            client = _get_client_bot()
            response = client.get_streams()
            streams = response.get("streams", []) if response.get("result") == "success" else []
            stream_exists = any(s.get("name") == "Agents-Channel" for s in streams)

            result = {
                "status": "success",
                "agent_id": agent_id,
                "instance_id": instance_id,
                "agent_type": agent_type,
                "stream": "Agents-Channel",
                "afk_enabled": True,
            }

            if not stream_exists:
                result["warning"] = "Stream 'Agents-Channel' does not exist."

            return result

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
                msg_info = _tracker.format_agent_message(
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
                        "afk_enabled": True,
                    }
                return {"status": "error", "error": result.get("msg", "Failed to send")}
            except Exception as e:
                track_tool_error("agent_message", type(e).__name__)
                return {"status": "error", "error": str(e)}


def wait_for_response(request_id: str) -> dict[str, Any]:
    """Wait for user response by polling the database."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "wait_for_response"}):
        track_tool_call("wait_for_response")
        try:
            db = get_database()

            # Blocking loop polling database every ~1s until status is terminal
            while True:
                result = db.query_one(
                    """
                    SELECT status, response, responded_at
                    FROM user_input_requests
                    WHERE request_id = ?
                    """,
                    [request_id],
                )

                if not result:
                    return {"status": "error", "error": "Request not found"}

                status, response, responded_at = result

                # Check if status is terminal
                if status in ["answered", "cancelled"]:
                    return {
                        "status": "success",
                        "request_status": status,
                        "response": response,
                        "responded_at": (
                            responded_at.isoformat() if responded_at else None
                        ),
                    }

                # Send agent status update periodically (every 30 seconds)
                # This is optional but helps with monitoring
                time.sleep(1.0)

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
            # TODO: Implement with DatabaseManager in Task 6
            return {
                "status": "success",
                "message": "Status updated (stub implementation)",
            }
        except Exception as e:
            track_tool_error("send_agent_status", type(e).__name__)
            return {"status": "error", "error": str(e)}


def request_user_input(
    agent_id: str, question: str, context: str = "", options: list[str] | None = None
) -> dict[str, Any]:
    """Request input from user via Zulip message."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "request_user_input"}):
        track_tool_call("request_user_input")
        try:
            request_id = str(uuid.uuid4())
            db = get_database()

            # Insert user input request into database
            db.execute(
                """
                INSERT INTO user_input_requests
                (request_id, agent_id, question, context, options, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    agent_id,
                    question,
                    context,
                    str(options) if options else None,
                    "pending",
                    datetime.utcnow(),
                ),
            )

            # Format message content
            message_content = f"""🤖 **Agent Request**

**Question**: {question}

**Context**: {context}"""

            if options:
                message_content += "\n\n**Options**:\n"
                for i, option in enumerate(options, 1):
                    message_content += f"{i}. {option}\n"
                message_content += "\nReply with the number of your choice or type your response."
            else:
                message_content += "\n\nPlease respond with your answer."

            message_content += f"\n\n*Request ID: `{request_id}`*"

            # Get agent info to determine user
            agent_data = db.query_one(
                "SELECT agent_type, metadata FROM agents WHERE agent_id = ?",
                [agent_id]
            )

            if not agent_data:
                return {"status": "error", "error": "Agent not found"}

            agent_type = agent_data[0]

            # For now, send to Agents-Channel stream since we don't have user mapping
            # TODO: In future, implement proper user detection from agent metadata
            from ..tools.messaging import send_message
            result = send_message(
                message_type="stream",
                to="Agents-Channel",
                content=message_content,
                topic=f"User Input Request - {agent_type}"
            )

            if result.get("status") != "success":
                return {"status": "error", "error": f"Failed to send message: {result.get('error')}"}

            return {"status": "success", "request_id": request_id, "message_sent": True}
        except Exception as e:
            track_tool_error("request_user_input", type(e).__name__)
            return {"status": "error", "error": str(e)}


def start_task(agent_id: str, name: str, description: str = "") -> dict[str, Any]:
    """Start a new task."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "start_task"}):
        track_tool_call("start_task")
        try:
            task_id = str(uuid.uuid4())
            db = get_database()

            # Insert task into database
            db.execute(
                """
                INSERT INTO tasks
                (task_id, agent_id, name, description, status, progress, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, agent_id, name, description, "started", 0, datetime.utcnow()),
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
            db = get_database()

            # Update task progress in database
            update_sql = "UPDATE tasks SET progress = ?"
            params = [progress]

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
            db = get_database()

            # Complete task in database
            db.execute(
                """
                UPDATE tasks
                SET status = ?, progress = ?, completed_at = ?, outputs = ?, metrics = ?
                WHERE task_id = ?
                """,
                ("completed", 100, datetime.utcnow(), outputs, metrics, task_id),
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
            db = get_database()

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


def register_agent_tools(mcp: Any) -> None:
    mcp.tool(description="Register agent and get topic")(register_agent)
    mcp.tool(description="Send agent message (AFK gated)")(agent_message)
    mcp.tool(description="Wait for human response")(wait_for_response)
    mcp.tool(description="Send agent status update")(send_agent_status)
    mcp.tool(description="Request input from user")(request_user_input)
    mcp.tool(description="Start a new task")(start_task)
    mcp.tool(description="Update task progress")(update_task_progress)
    mcp.tool(description="Complete a task")(complete_task)
    mcp.tool(description="List agent instances")(list_instances)
