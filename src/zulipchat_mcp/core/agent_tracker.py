"""Lightweight agent instance tracking for ZulipChat MCP.

This module provides simple, file-based tracking of AI agent instances
and communication state.
"""

import json
import logging
import os
import platform
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..utils.topics import topic_chat, project_from_path

logger = logging.getLogger(__name__)


class AgentTracker:
    """Simple agent instance tracker using project-local storage.

    Uses the `.mcp/` directory under the current working directory for any
    temporary state. AFK is maintained as a runtime (in-memory) flag and is
    not persisted across runs.
    """

    # Configuration directory (project-local)
    CONFIG_DIR = Path.cwd() / ".mcp"

    # File paths
    AFK_STATE_FILE = CONFIG_DIR / "afk_state.json"  # kept for backward compat, unused
    AGENT_REGISTRY_FILE = CONFIG_DIR / "agent_registry.json"
    PENDING_RESPONSES_FILE = CONFIG_DIR / "pending_responses.json"

    # Standard channel name
    AGENTS_CHANNEL = "Agents-Channel"

    def __init__(self):
        """Initialize the agent tracker."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = str(uuid.uuid4())[:8]  # Short session ID
        # Runtime AFK flag (not persisted)
        self.afk_enabled: bool = False

    # ... rest of the implementation remains the same as the previous version
    
    def register_agent(self, agent_type: str = "claude-code") -> dict[str, Any]:
        """Register an agent instance and save to registry.

        Args:
            agent_type: Type of agent (claude-code, gemini, cursor, etc.)

        Returns:
            Registration info including stream name and topic
        """
        identity = self.get_instance_identity()

        # Consistent chat topic
        project_name = identity.get("project", "Project")
        topic = topic_chat(project_name, agent_type, self.session_id)

        # Always use standard Agents-Channel
        stream_name = self.AGENTS_CHANNEL

        # Create registration record
        registration = {
            "agent_type": agent_type,
            "session_id": self.session_id,
            "stream": stream_name,
            "topic": topic,
            "identity": identity,
            "registered_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }

        # Save to registry
        self._update_agent_registry(registration)

        return {
            "status": "success",
            "stream": stream_name,
            "topic": topic,
            "session_id": self.session_id,
            "identity": identity,
            "message": f"Agent registered to {stream_name}/{topic}",
        }

    # ... rest of the implementation follows the same pattern as the previous version