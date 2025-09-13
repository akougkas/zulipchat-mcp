"""Agent registry for managing AI agents in Zulip."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Prefer v2.5 core client directly (avoid top-level wrappers)
    from ..config import ConfigManager
    from ..core.client import ZulipClientWrapper


class AgentDatabase:
    """Mock database for agent registration."""

    def __init__(self, db_url: str) -> None:
        """Initialize the agent database.

        Args:
            db_url: Database URL
        """
        self.db_url = db_url
        self.agents: dict[str, dict[str, Any]] = {}

    def register_agent(self, name: str, agent_type: str, active: bool) -> bool:
        """Register an agent.

        Args:
            name: Agent name
            agent_type: Type of agent
            active: Whether agent is active

        Returns:
            Success status
        """
        self.agents[name] = {
            "name": name,
            "type": agent_type,
            "active": active,
        }
        return True


class AgentRegistry:
    """Registry for managing AI agents in Zulip."""

    def __init__(self, config: ConfigManager, client: ZulipClientWrapper) -> None:
        """Initialize the agent registry.

        Args:
            config: Configuration manager
            client: Zulip client wrapper
        """
        self.config = config
        self.client = client
        self.db = AgentDatabase(getattr(config, "DATABASE_URL", ""))

    def register_agent(
        self, name: str, agent_type: str, active: bool = True
    ) -> dict[str, Any]:
        """Register a new agent.

        Args:
            name: Agent name
            agent_type: Type of agent
            active: Whether agent is active

        Returns:
            Registration result
        """
        try:
            # Get or create stream for agent
            stream_prefix = getattr(
                self.config, "DEFAULT_AGENT_STREAM_PREFIX", "ai-agents"
            )
            stream_name = f"{stream_prefix}/{name}"

            # Check if stream exists
            streams_resp = self.client.get_streams()
            streams = (
                streams_resp.get("streams", [])
                if streams_resp.get("result") == "success"
                else []
            )
            stream_exists = any(s.get("name") == stream_name for s in streams)

            if not stream_exists:
                # Create stream via subscriptions
                result = self.client.client.add_subscriptions(
                    streams=[{"name": stream_name}]
                )
                if result.get("result") != "success":
                    return {
                        "status": "error",
                        "error": f"Failed to create stream: {result}",
                    }

            # Register in database
            if not self.db.register_agent(name, agent_type, active):
                return {
                    "status": "error",
                    "error": "Failed to register agent in database",
                }

            # Send welcome message
            self.client.send_message(
                message_type="stream",
                to=stream_name,
                topic="Registration",
                content=f"Agent '{name}' registered successfully!",
            )

            return {
                "status": "success",
                "agent": {
                    "name": name,
                    "type": agent_type,
                    "active": active,
                    "stream": stream_name,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
