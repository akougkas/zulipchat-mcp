"""Agent communication module for Zulip MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Prefer v2.5 core client directly (avoid top-level wrappers)
    from ..config import ConfigManager
    from ..core.client import ZulipClientWrapper


class AgentCommunication:
    """Handle agent-to-agent communication in Zulip."""

    def __init__(self, config: ConfigManager, client: ZulipClientWrapper) -> None:
        """Initialize agent communication.

        Args:
            config: Configuration manager
            client: Zulip client wrapper
        """
        self.config = config
        self.client = client

    def send_agent_message(
        self,
        agent_name: str,
        message: str,
        topic: str = "agent-communication",
    ) -> dict[str, Any]:
        """Send a message to another agent.

        Args:
            agent_name: Target agent name
            message: Message content
            topic: Message topic

        Returns:
            Result of message send
        """
        try:
            # Get agent stream
            stream_prefix = getattr(
                self.config, "DEFAULT_AGENT_STREAM_PREFIX", "ai-agents"
            )
            stream_name = f"{stream_prefix}/{agent_name}"

            # Send message using core client wrapper signature
            return self.client.send_message(
                message_type="stream",
                to=stream_name,
                content=message,
                topic=topic,
            )
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
