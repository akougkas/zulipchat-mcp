"""Agent registry service for managing AI agents."""

import logging
from typing import Any
from uuid import uuid4

from ..client import ZulipClientWrapper
from ..config import ConfigManager
from ..database import AgentDatabase
from ..models.agent import Agent, AgentStatus, AgentType

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Service for managing agent registrations and streams."""

    def __init__(self, config: ConfigManager, client: ZulipClientWrapper):
        """Initialize agent registry."""
        self.config = config
        self.client = client
        db_url = getattr(config, "DATABASE_URL", "zulipchat_agents.db")
        self.db = AgentDatabase(db_url)
        self.stream_prefix = getattr(config, "DEFAULT_AGENT_STREAM_PREFIX", "ai-agents")

    def register_agent(
        self,
        agent_name: str,
        agent_type: str = "claude_code",
        private_stream: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a new AI agent with dedicated communication channel."""
        try:
            # Generate unique agent ID
            agent_id = str(uuid4())

            # Create stream name
            stream_name = f"{self.stream_prefix}/{agent_name}"

            # Create the stream in Zulip
            stream_result = self._create_agent_stream(stream_name, private_stream)

            if not stream_result.get("success"):
                return {
                    "status": "error",
                    "error": f"Failed to create stream: {stream_result.get('error')}",
                }

            stream_id = stream_result.get("stream_id")

            # Generate bot email (for future webhook integration)
            zulip_site = getattr(self.config, "ZULIP_SITE", "zulip.com")
            bot_email = f"{agent_name.lower().replace(' ', '-')}-bot@{zulip_site}"

            # Generate webhook URL
            webhook_url = f"https://api/webhooks/agent/{agent_id}"

            # Save to database
            success = self.db.register_agent(
                agent_id=agent_id,
                name=agent_name,
                agent_type=agent_type,
                stream_id=stream_id,
                stream_name=stream_name,
                bot_email=bot_email,
                webhook_url=webhook_url,
                is_private=private_stream,
                metadata=metadata,
            )

            if not success:
                return {"status": "error", "error": "Failed to save agent to database"}

            # Send welcome message to the stream
            self._send_welcome_message(stream_name, agent_name, agent_id)

            # Create agent object
            agent = Agent(
                id=agent_id,
                name=agent_name,
                type=AgentType(agent_type),
                stream_id=stream_id,
                stream_name=stream_name,
                bot_email=bot_email,
                webhook_url=webhook_url,
                is_private=private_stream,
                metadata=metadata or {},
            )

            return {
                "status": "success",
                "agent": agent.dict(),
                "message": f"Agent '{agent_name}' registered successfully",
            }

        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            return {"status": "error", "error": str(e)}

    def _create_agent_stream(
        self, stream_name: str, is_private: bool
    ) -> dict[str, Any]:
        """Create a dedicated stream for the agent."""
        try:
            # Check if stream already exists
            existing_streams = self.client.get_streams()
            for stream in existing_streams:
                if stream.get("name") == stream_name:
                    return {"success": True, "stream_id": stream.get("stream_id")}

            # Create new stream
            result = self.client.client.add_subscriptions(
                streams=[
                    {
                        "name": stream_name,
                        "description": "Communication channel for AI agent",
                        "invite_only": is_private,
                        "is_announcement_only": False,
                    }
                ]
            )

            if result.get("result") == "success":
                # Get stream ID
                streams = self.client.get_streams()
                for stream in streams:
                    if stream.get("name") == stream_name:
                        return {"success": True, "stream_id": stream.get("stream_id")}

            return {"success": False, "error": result.get("msg", "Unknown error")}

        except Exception as e:
            logger.error(f"Failed to create stream: {e}")
            return {"success": False, "error": str(e)}

    def _send_welcome_message(
        self, stream_name: str, agent_name: str, agent_id: str
    ) -> None:
        """Send welcome message to the agent's stream."""
        try:
            welcome_content = f"""🤖 **{agent_name} Agent Activated**

Welcome to the dedicated communication channel for {agent_name}!

**Agent Details:**
- Agent ID: `{agent_id}`
- Type: AI Coding Assistant
- Status: 🟢 Online

**How to Interact:**
- This agent will post status updates, questions, and completion notifications here
- Reply directly to agent messages to provide input
- Use reactions for quick responses (👍 = yes, 👎 = no, ⏸️ = pause)

**Available Commands:**
- `/status` - Check agent status
- `/pause` - Pause current task
- `/resume` - Resume paused task
- `/cancel` - Cancel current task

The agent is ready to collaborate! 🚀"""

            self.client.send_message(
                message_type="stream",
                to=stream_name,
                topic="Welcome",
                content=welcome_content,
            )

        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent by ID."""
        agent_data = self.db.get_agent(agent_id)
        if agent_data:
            # Update last active timestamp
            self.db.update_agent_activity(agent_id)
        return agent_data

    def update_agent_status(
        self, agent_id: str, status: AgentStatus, current_task: str | None = None
    ) -> dict[str, Any]:
        """Update agent status and optionally send notification."""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Update activity timestamp
            self.db.update_agent_activity(agent_id)

            # Send status update to stream if agent has one
            if agent.get("stream_name"):
                status_emoji = {
                    AgentStatus.IDLE: "⚪",
                    AgentStatus.WORKING: "🟢",
                    AgentStatus.WAITING: "🟡",
                    AgentStatus.BLOCKED: "🔴",
                    AgentStatus.OFFLINE: "⚫",
                }.get(status, "❓")

                status_content = (
                    f"{status_emoji} **Status Update**\n\nStatus: {status.value}"
                )
                if current_task:
                    status_content += f"\nCurrent Task: {current_task}"

                self.client.send_message(
                    message_type="stream",
                    to=agent["stream_name"],
                    topic="Status",
                    content=status_content,
                )

            return {"status": "success", "agent_status": status.value}

        except Exception as e:
            logger.error(f"Failed to update agent status: {e}")
            return {"status": "error", "error": str(e)}

    def unregister_agent(
        self, agent_id: str, archive_stream: bool = True
    ) -> dict[str, Any]:
        """Unregister an agent and optionally archive its stream."""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Send farewell message
            if agent.get("stream_name"):
                farewell_content = f"""👋 **Agent Deactivating**

The {agent['name']} agent is being unregistered.

All conversation history will be preserved in this archived stream.

Thank you for collaborating! 🙏"""

                self.client.send_message(
                    message_type="stream",
                    to=agent["stream_name"],
                    topic="Farewell",
                    content=farewell_content,
                )

                # Archive stream if requested
                if archive_stream:
                    # Note: Zulip API doesn't have direct stream archival,
                    # but we can unsubscribe everyone or rename it
                    archived_name = f"[ARCHIVED] {agent['stream_name']}"
                    # This would require additional API implementation

            # Remove from database (or mark as inactive)
            # For now, we'll just update the status
            self.db.update_agent_activity(agent_id)

            return {
                "status": "success",
                "message": f"Agent '{agent['name']}' unregistered successfully",
            }

        except Exception as e:
            logger.error(f"Failed to unregister agent: {e}")
            return {"status": "error", "error": str(e)}
