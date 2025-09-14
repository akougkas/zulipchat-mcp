"""Agent communication tools for ZulipChat MCP v2.5.1.

Agent-specific functionality extracted from original events.py.
Requires database for persistence and AFK mode management.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from ..core.client import ZulipClientWrapper
from ..config import ConfigManager

# Import optional components
try:
    from ..utils.database_manager import DatabaseManager
    from ..core.agent_tracker import AgentTracker
    from ..utils.topics import project_from_path, topic_input, topic_chat
    database_available = True
except ImportError:
    database_available = False


async def register_agent(agent_type: str = "claude-code") -> dict[str, Any]:
    """Register agent and create database records."""
    if not database_available:
        return {"status": "error", "error": "Database not available for agent features"}

    try:
        db = DatabaseManager()
        agent_id = str(uuid.uuid4())
        instance_id = str(uuid.uuid4())

        # Insert agent record
        db.execute(
            "INSERT OR REPLACE INTO agents (agent_id, agent_type, created_at, metadata) VALUES (?, ?, ?, ?)",
            (agent_id, agent_type, datetime.utcnow(), "{}"),
        )

        # Insert agent instance
        db.execute(
            """INSERT INTO agent_instances
               (instance_id, agent_id, session_id, project_dir, host, started_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (instance_id, agent_id, str(uuid.uuid4())[:8], str(os.getcwd()),
             os.getenv("HOSTNAME", "localhost"), datetime.utcnow()),
        )

        # Initialize AFK state
        db.execute(
            "INSERT OR REPLACE INTO afk_state (id, is_afk, reason, updated_at) VALUES (1, ?, ?, ?)",
            (False, "Agent ready for normal operations", datetime.utcnow()),
        )

        return {
            "status": "success",
            "agent_id": agent_id,
            "instance_id": instance_id,
            "agent_type": agent_type,
            "stream": "Agents-Channel",
            "afk_enabled": False,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def agent_message(
    content: str,
    require_response: bool = False,
    agent_type: str = "claude-code",
) -> dict[str, Any]:
    """Send bot-authored messages to users via Agents-Channel."""
    if not database_available:
        return {"status": "skipped", "reason": "Database not available for agent features"}

    try:
        # Check AFK state
        db = DatabaseManager()
        afk_state = db.get_afk_state() or {}
        dev_override = os.getenv("ZULIP_DEV_NOTIFY", "0") in ("1", "true", "True")

        if not afk_state.get("is_afk") and not dev_override:
            return {"status": "skipped", "reason": "AFK disabled; notifications gated"}

        # Get agent tracker and format message
        tracker = AgentTracker()
        msg_info = tracker.format_agent_message(content, agent_type, require_response)

        if msg_info["status"] != "ready":
            return msg_info

        # Send message using bot identity
        config = ConfigManager()
        client = ZulipClientWrapper(config, use_bot_identity=True)

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
        else:
            return {"status": "error", "error": result.get("msg", "Failed to send")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def enable_afk_mode(hours: int = 8, reason: str = "Away from computer") -> dict[str, Any]:
    """Enable AFK mode for automatic notifications."""
    if not database_available:
        return {"status": "error", "error": "Database not available for AFK features"}

    try:
        DatabaseManager().set_afk_state(enabled=True, reason=reason, hours=hours)
        return {
            "status": "success",
            "message": f"AFK mode enabled for {hours} hours",
            "reason": reason,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def disable_afk_mode() -> dict[str, Any]:
    """Disable AFK mode and restore normal operation."""
    if not database_available:
        return {"status": "error", "error": "Database not available for AFK features"}

    try:
        DatabaseManager().set_afk_state(enabled=False, reason="", hours=0)
        return {"status": "success", "message": "AFK mode disabled - normal operation"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_afk_status() -> dict[str, Any]:
    """Query current AFK mode status."""
    if not database_available:
        return {"status": "success", "afk_state": {"enabled": False, "reason": "Database not available"}}

    try:
        state = DatabaseManager().get_afk_state() or {}
        normalized = {
            "enabled": bool(state.get("is_afk")),
            "reason": state.get("reason"),
            "updated_at": state.get("updated_at"),
        }
        return {"status": "success", "afk_state": normalized}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_events_tools(mcp: FastMCP) -> None:
    """Register agent communication tools with the MCP server."""
    # Agent communication tools (if database available)
    if database_available:
        mcp.tool(name="register_agent", description="Register AI agent instance and create database records")(register_agent)
        mcp.tool(name="agent_message", description="Send bot-authored messages via Agents-Channel")(agent_message)
        mcp.tool(name="enable_afk_mode", description="Enable AFK mode for automatic notifications")(enable_afk_mode)
        mcp.tool(name="disable_afk_mode", description="Disable AFK mode and restore normal operation")(disable_afk_mode)
        mcp.tool(name="get_afk_status", description="Query current AFK mode status")(get_afk_status)