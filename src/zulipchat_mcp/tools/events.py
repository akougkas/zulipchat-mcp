"""Event system tools for ZulipChat MCP v2.5.1.

Complete event handling including registration, polling, listening, and agent communication.
All functionality from the complex v25 architecture preserved in minimal code.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager

# Import optional components
try:
    from ..utils.database_manager import DatabaseManager
    from ..core.agent_tracker import AgentTracker
    from ..utils.topics import project_from_path, topic_input, topic_chat
    database_available = True
except ImportError:
    database_available = False


async def register_events(
    event_types: list[str],
    narrow: list[dict[str, Any]] | None = None,
    queue_lifespan_secs: int = 300,
    all_public_streams: bool = False,
    include_subscribers: bool = False,
    client_gravatar: bool = False,
    slim_presence: bool = False,
    # Fetch event types for initial state
    fetch_event_types: list[str] | None = None,
    # Client capabilities
    client_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register for comprehensive real-time event streams from Zulip."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        register_params = {
            "event_types": event_types,
            "queue_lifespan_secs": min(queue_lifespan_secs, 600),  # Max 600 seconds
            "all_public_streams": all_public_streams,
            "include_subscribers": include_subscribers,
            "client_gravatar": client_gravatar,
            "slim_presence": slim_presence,
        }

        if narrow:
            register_params["narrow"] = narrow
        if fetch_event_types:
            register_params["fetch_event_types"] = fetch_event_types
        if client_capabilities:
            register_params["client_capabilities"] = client_capabilities

        result = client.register(**register_params)

        if result.get("result") == "success":
            return {
                "status": "success",
                "queue_id": result.get("queue_id"),
                "last_event_id": result.get("last_event_id", -1),
                "zulip_feature_level": result.get("zulip_feature_level"),
                "realm_state": result.get("realm_state", {}),
                "queue_lifespan_secs": queue_lifespan_secs,
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to register events")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_events(
    queue_id: str,
    last_event_id: int,
    dont_block: bool = False,
    timeout: int = 10,
    apply_markdown: bool = True,
    client_gravatar: bool = False,
    user_client: str | None = None,
) -> dict[str, Any]:
    """Poll events from registered queue with long-polling support."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_events(
            queue_id=queue_id,
            last_event_id=last_event_id,
            dont_block=dont_block,
            timeout=min(timeout, 60),  # Max 60 seconds
            apply_markdown=apply_markdown,
            client_gravatar=client_gravatar,
        )

        if result.get("result") == "success":
            events = result.get("events", [])
            return {
                "status": "success",
                "events": events,
                "found_newest": result.get("found_newest", False),
                "queue_id": queue_id,
                "event_count": len(events),
                "last_event_id": max([e.get("id", last_event_id) for e in events], default=last_event_id),
            }
        else:
            return {"status": "error", "error": result.get("msg", "Failed to get events")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def listen_events(
    event_types: list[str],
    duration: int = 300,  # Max 600 seconds
    narrow: list[dict[str, Any]] | None = None,
    filters: dict[str, Any] | None = None,
    poll_interval: int = 1,
    max_events_per_poll: int = 100,
    all_public_streams: bool = False,
    callback_url: str | None = None,
) -> dict[str, Any]:
    """Comprehensive stateless event listener with automatic queue management."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Register queue
        register_result = await register_events(
            event_types=event_types,
            narrow=narrow,
            queue_lifespan_secs=min(duration + 60, 600),  # Buffer for processing
            all_public_streams=all_public_streams,
        )

        if register_result.get("status") != "success":
            return register_result

        queue_id = register_result["queue_id"]
        last_event_id = register_result["last_event_id"]
        collected_events = []
        start_time = time.time()

        try:
            # Event collection loop
            while time.time() - start_time < duration:
                # Get events
                events_result = await get_events(
                    queue_id=queue_id,
                    last_event_id=last_event_id,
                    timeout=min(poll_interval, 30),
                )

                if events_result.get("status") == "success":
                    events = events_result.get("events", [])

                    # Apply filters if specified
                    if filters and events:
                        filtered_events = []
                        for event in events:
                            include_event = True
                            for filter_key, filter_value in filters.items():
                                if filter_key in event and event[filter_key] != filter_value:
                                    include_event = False
                                    break
                            if include_event:
                                filtered_events.append(event)
                        events = filtered_events

                    if events:
                        collected_events.extend(events[:max_events_per_poll])
                        last_event_id = max([e.get("id", last_event_id) for e in events], default=last_event_id)

                        # Send to webhook if configured
                        if callback_url:
                            try:
                                import httpx
                                async with httpx.AsyncClient() as http_client:
                                    await http_client.post(callback_url, json={"events": events})
                            except Exception:
                                pass  # Best effort

                # Sleep before next poll
                await asyncio.sleep(poll_interval)

        finally:
            # Cleanup: deregister queue
            try:
                await deregister_events(queue_id)
            except Exception:
                pass  # Best effort cleanup

        return {
            "status": "success",
            "collected_events": collected_events,
            "event_count": len(collected_events),
            "duration_seconds": time.time() - start_time,
            "session_summary": {
                "queue_id": queue_id,
                "event_types": event_types,
                "poll_interval": poll_interval,
                "max_events_per_poll": max_events_per_poll,
            }
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# Agent communication tools (if database available)
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


async def deregister_events(queue_id: str) -> dict[str, Any]:
    """Deregister event queue."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        result = client.deregister(queue_id)

        if result.get("result") == "success":
            return {"status": "success", "queue_id": queue_id}
        else:
            return {"status": "error", "error": result.get("msg", "Failed to deregister queue")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_events_tools(mcp: FastMCP) -> None:
    """Register event tools with the MCP server."""
    mcp.tool(name="register_events", description="Register for comprehensive real-time event streams")(register_events)
    mcp.tool(name="get_events", description="Poll events from registered queue with long-polling")(get_events)
    mcp.tool(name="listen_events", description="Comprehensive stateless event listener with webhook integration")(listen_events)
    mcp.tool(name="deregister_events", description="Deregister event queue")(deregister_events)

    # Agent communication tools (if database available)
    if database_available:
        mcp.tool(name="register_agent", description="Register AI agent instance and create database records")(register_agent)
        mcp.tool(name="agent_message", description="Send bot-authored messages via Agents-Channel")(agent_message)
        mcp.tool(name="enable_afk_mode", description="Enable AFK mode for automatic notifications")(enable_afk_mode)
        mcp.tool(name="disable_afk_mode", description="Disable AFK mode and restore normal operation")(disable_afk_mode)
        mcp.tool(name="get_afk_status", description="Query current AFK mode status")(get_afk_status)