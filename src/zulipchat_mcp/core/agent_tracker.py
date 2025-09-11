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
    AGENTS_CHANNEL = "Agent-Channel"

    def __init__(self):
        """Initialize the agent tracker."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = str(uuid.uuid4())[:8]  # Short session ID
        # Runtime AFK flag (not persisted)
        self.afk_enabled: bool = False

    def get_instance_identity(self) -> dict[str, str]:
        """Get current instance identity from environment.

        Returns a dict with:
        - project: Current project name (from git or directory)
        - branch: Current git branch if available
        - hostname: Machine hostname
        - platform: OS platform
        - user: Current user
        """
        identity = {
            "hostname": platform.node(),
            "platform": platform.system(),
            "user": os.environ.get("USER", "unknown"),
            "timestamp": datetime.now().isoformat(),
        }

        # Try to get project info from git
        try:
            # Get current directory name as fallback
            cwd = Path.cwd()
            identity["project"] = cwd.name

            # Try to get git info
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                git_root = Path(result.stdout.strip())
                identity["project"] = git_root.name

                # Get branch name
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if branch_result.returncode == 0:
                    identity["branch"] = branch_result.stdout.strip() or "main"
        except Exception as e:
            logger.debug(f"Could not get git info: {e}")

        return identity

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

        # Always use standard Agent-Channel
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

    def _update_agent_registry(self, registration: dict) -> None:
        """Update the agent registry file."""
        try:
            # Load existing registry
            if self.AGENT_REGISTRY_FILE.exists():
                registry = json.loads(self.AGENT_REGISTRY_FILE.read_text())
            else:
                registry = {"agents": []}

            # Add new registration
            registry["agents"].append(registration)

            # Keep only last 100 registrations
            registry["agents"] = registry["agents"][-100:]

            # Save back
            self.AGENT_REGISTRY_FILE.write_text(json.dumps(registry, indent=2))
        except Exception as e:
            logger.error(f"Failed to update agent registry: {e}")

    def get_active_agents(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get list of recently active agents.

        Args:
            hours: How many hours back to look for active agents
        """
        try:
            if not self.AGENT_REGISTRY_FILE.exists():
                return []

            registry = json.loads(self.AGENT_REGISTRY_FILE.read_text())
            cutoff = datetime.now() - timedelta(hours=hours)

            active_agents = []
            for agent in registry.get("agents", []):
                last_active = datetime.fromisoformat(agent["last_active"])
                if last_active > cutoff:
                    active_agents.append(agent)

            return active_agents
        except Exception as e:
            logger.error(f"Failed to get active agents: {e}")
            return []

    def get_afk_state(self) -> dict[str, Any]:
        """Get current AFK state (runtime only)."""
        # Runtime-only AFK per v2 design. Not persisted.
        return {
            "enabled": self.afk_enabled,
            "reason": None,
            "expires_at": None,
            "set_at": None,
        }

    def set_afk(
        self, enabled: bool, reason: str | None = None, hours: float = 8
    ) -> dict[str, Any]:
        """Set AFK state (runtime only)."""
        self.afk_enabled = bool(enabled)
        return {
            "status": "success",
            "afk_enabled": self.afk_enabled,
            "message": f"AFK mode {'enabled' if self.afk_enabled else 'disabled'}",
            "expires_in_hours": hours if self.afk_enabled else None,
        }

    def should_notify(self) -> bool:
        """Check if notifications should be sent (only when AFK is enabled)."""
        state = self.get_afk_state()
        return state.get("enabled", False)

    def format_agent_message(
        self,
        content: str,
        agent_type: str = "claude-code",
        require_response: bool = False,
    ) -> dict[str, Any]:
        """Format an agent message with proper routing.

        Args:
            content: Message content
            agent_type: Type of agent
            require_response: Whether this message expects a response

        Returns:
            Dict with stream, topic, and formatted content
        """
        # Get or create registration
        if not hasattr(self, "_current_registration"):
            self._current_registration = self.register_agent(agent_type)

        reg_info = self._current_registration

        # AFK mode is only for special cases when user is away
        # Normal agent communication works regardless of AFK state
        # AFK only affects automatic notifications, not direct agent messages

        # Format the message with session info
        identity = reg_info["identity"]
        header = f"[{agent_type}@{identity['project']}]"

        formatted_content = f"{header} {content}"

        # If response required, create a pending response entry
        response_id = None
        if require_response:
            response_id = self._create_pending_response(agent_type, content)
            formatted_content += (
                f"\n\n_Reply with: @response {response_id} [your message]_"
            )

        return {
            "status": "ready",
            "stream": reg_info["stream"],
            "topic": reg_info["topic"],
            "content": formatted_content,
            "response_id": response_id,
            "afk_enabled": self.afk_enabled,
        }

    def _create_pending_response(self, agent_type: str, prompt: str) -> str:
        """Create a pending response entry."""
        try:
            response_id = str(uuid.uuid4())[:8]

            # Load existing responses
            if self.PENDING_RESPONSES_FILE.exists():
                responses = json.loads(self.PENDING_RESPONSES_FILE.read_text())
            else:
                responses = {"pending": {}}

            # Add new pending response
            responses["pending"][response_id] = {
                "agent_type": agent_type,
                "session_id": self.session_id,
                "prompt": prompt,
                "created_at": datetime.now().isoformat(),
                "status": "waiting",
            }

            # Clean old responses (older than 24 hours)
            cutoff = datetime.now() - timedelta(hours=24)
            for rid, data in list(responses["pending"].items()):
                created = datetime.fromisoformat(data["created_at"])
                if created < cutoff:
                    del responses["pending"][rid]

            # Save back
            self.PENDING_RESPONSES_FILE.write_text(json.dumps(responses, indent=2))
            return response_id

        except Exception as e:
            logger.error(f"Failed to create pending response: {e}")
            return str(uuid.uuid4())[:8]

    def check_for_response(self, response_id: str) -> dict[str, Any] | None:
        """Check if a response has been received."""
        try:
            if not self.PENDING_RESPONSES_FILE.exists():
                return None

            responses = json.loads(self.PENDING_RESPONSES_FILE.read_text())
            response_data = responses["pending"].get(response_id)

            if response_data and response_data.get("response"):
                # Mark as received and return
                response_data["status"] = "received"
                self.PENDING_RESPONSES_FILE.write_text(json.dumps(responses, indent=2))
                return {
                    "response": response_data["response"],
                    "responded_at": response_data.get("responded_at"),
                    "status": "received",
                }

            return None

        except Exception as e:
            logger.error(f"Failed to check for response: {e}")
            return None
