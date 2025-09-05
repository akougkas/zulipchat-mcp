"""Agent communication tools for ZulipChat MCP."""

import logging
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from ..afk_state import get_afk_state
from ..client import ZulipClientWrapper
from ..config import ConfigManager
from ..database import AgentDatabase
from ..instance_identity import get_instance_identity
from ..models.agent import AgentStatus, InputRequest
from ..services.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class AgentCommunication:
    """Tools for agent-to-human communication via Zulip."""

    def __init__(self, config: ConfigManager, client: ZulipClientWrapper):
        """Initialize agent communication tools."""
        self.config = config
        self.client = client
        db_url = getattr(config, "DATABASE_URL", "zulipchat_agents.db")
        self.db = AgentDatabase(db_url)
        self.registry = AgentRegistry(config, client)
        self.timeout_seconds = 300  # Default timeout for input requests

    def agent_message(
        self,
        agent_id: str,
        message_type: Literal["status", "question", "completion", "error"],
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a message from agent to human via Zulip."""
        try:
            # Check AFK state - only send messages when AFK is active
            afk_state = get_afk_state()
            if not afk_state.is_afk():
                # Not AFK, don't send notifications
                return {
                    "status": "skipped",
                    "reason": "Not in AFK mode - notifications disabled",
                }

            # Get instance identity for smart routing
            instance = get_instance_identity()

            # Get agent details
            agent = self.registry.get_agent(agent_id)
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Add instance prefix to content
            instance_prefix = instance.get_notification_prefix()

            # Format message based on type
            formatted_content = self._format_agent_message(
                agent["name"], message_type, content, metadata
            )

            # Prepend instance info
            formatted_content = f"{instance_prefix}\n{formatted_content}"

            # Use instance-aware stream and topic
            stream_name = (
                instance.get_stream_name()
            )  # Personal stream like "claude-code-username"
            topic = (
                instance.get_topic_name()
            )  # Project-specific topic like "project-name - hostname"

            # Send message to the personal stream with project topic
            result = self.client.send_message(
                message_type="stream",
                to=stream_name,
                topic=topic,
                content=formatted_content,
            )

            # Save message to database
            if result.get("result") == "success":
                message_id = str(uuid4())
                zulip_message_id = result.get("id")
                self.db.save_agent_message(
                    message_id=message_id,
                    agent_id=agent_id,
                    message_type=message_type,
                    content=content,
                    metadata=metadata,
                    zulip_message_id=zulip_message_id,
                )

                return {
                    "status": "success",
                    "message_id": message_id,
                    "zulip_message_id": zulip_message_id,
                }

            return {
                "status": "error",
                "error": result.get("msg", "Failed to send message"),
            }

        except Exception as e:
            logger.error(f"Failed to send agent message: {e}")
            return {"status": "error", "error": str(e)}

    def _format_agent_message(
        self,
        agent_name: str,
        message_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Format agent message with appropriate styling and clear bot identity."""
        emoji_map = {
            "status": "📊",
            "question": "❓",
            "completion": "✅",
            "error": "❌",
        }

        emoji = emoji_map.get(message_type, "🤖")

        # Add clear bot identity header
        identity_header = ""
        if self.client.identity == "bot":
            # Using bot identity directly
            identity_header = f"{emoji} **{agent_name}** (AI Assistant)\n"
        else:
            # Sent via user account, make it clear it's from Claude Code
            identity_header = f"{emoji} **{agent_name}** (via MCP integration)\n"
            identity_header += "*Sent by: Claude Code*\n"
            identity_header += "─" * 40 + "\n"

        formatted = identity_header + f"\n{content}"

        if metadata:
            formatted += "\n\n" + "─" * 40
            if "files" in metadata:
                formatted += f"\n📁 **Files:** {', '.join(metadata['files'])}"
            if "progress" in metadata:
                # Create visual progress bar
                progress = metadata["progress"]
                filled = int(progress / 10)
                empty = 10 - filled
                progress_bar = "█" * filled + "░" * empty
                formatted += f"\n📈 **Progress:** {progress_bar} {progress}%"
            if "duration" in metadata:
                formatted += f"\n⏱️ **Duration:** {metadata['duration']}"
            if "task" in metadata:
                formatted += f"\n📋 **Task:** {metadata['task']}"

        return formatted

    def request_user_input(
        self,
        agent_id: str,
        question: str,
        context: dict[str, Any],
        options: list[str] | None = None,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        """Request input from user with context and options."""
        try:
            # Get agent details
            agent = self.registry.get_agent(agent_id)
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Create input request
            request_id = str(uuid4())
            request = InputRequest(
                id=request_id,
                agent_id=agent_id,
                question=question,
                context=context,
                options=options,
                timeout_seconds=timeout_seconds,
            )

            # Save to database
            self.db.create_input_request(
                request_id=request.id,
                agent_id=agent_id,
                question=question,
                context=context,
                options=options,
                timeout_seconds=timeout_seconds,
            )

            # Format and send message
            formatted_content = self._format_input_request(question, context, options)

            result = self.client.send_message(
                message_type="stream",
                to=agent["stream_name"],
                topic="Input Required",
                content=formatted_content,
            )

            if result.get("result") == "success":
                return {
                    "status": "success",
                    "request_id": request_id,
                    "message": "Input request sent. Use wait_for_response to get the answer.",
                }

            return {
                "status": "error",
                "error": result.get("msg", "Failed to send request"),
            }

        except Exception as e:
            logger.error(f"Failed to request user input: {e}")
            return {"status": "error", "error": str(e)}

    def _format_input_request(
        self,
        question: str,
        context: dict[str, Any],
        options: list[str] | None = None,
    ) -> str:
        """Format input request message."""
        formatted = f"🤖 **Input Required**\n\n**Question:** {question}\n\n"

        if context:
            formatted += "**Context:**\n"
            for key, value in context.items():
                formatted += f"- {key}: {value}\n"
            formatted += "\n"

        if options:
            formatted += "**Options:**\n"
            for i, option in enumerate(options, 1):
                number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
                emoji = number_emojis[i - 1] if i <= 9 else f"{i}."
                formatted += f"{emoji} {option}\n"
            formatted += "\n*Reply with number or custom response*"
        else:
            formatted += "*Please reply with your response*"

        return formatted

    def wait_for_response(
        self, agent_id: str, request_id: str, timeout: int = 300
    ) -> str | None:
        """Wait for user response to a specific request.

        Note: This is a synchronous polling implementation.
        For async operations, consider using a webhook or message queue.
        """
        import time

        start_time = datetime.now()

        while (datetime.now() - start_time).total_seconds() < timeout:
            # Check database for response
            request = self.db.get_pending_request(request_id)

            if request and request.get("is_answered"):
                return request.get("response")

            # Wait before checking again
            time.sleep(2)

        # Timeout reached
        logger.warning(f"Timeout waiting for response to request {request_id}")
        return None

    def send_agent_status(
        self,
        agent_id: str,
        status: Literal["working", "waiting", "blocked", "idle"],
        current_task: str,
        progress_percentage: int | None = None,
        estimated_time: str | None = None,
    ) -> dict[str, Any]:
        """Send live status update from agent."""
        try:
            # Get agent details
            agent = self.registry.get_agent(agent_id)
            if not agent:
                return {"status": "error", "error": "Agent not found"}

            # Format status message
            status_emoji = {
                "working": "🟢",
                "waiting": "🟡",
                "blocked": "🔴",
                "idle": "⚪",
            }.get(status, "❓")

            content = "🔄 **Status Update**\n\n"
            content += f"**Status:** {status_emoji} {status.capitalize()}\n"
            content += f"**Current Task:** {current_task}\n"

            if progress_percentage is not None:
                # Create progress bar
                filled = int(progress_percentage / 10)
                empty = 10 - filled
                progress_bar = "█" * filled + "░" * empty
                content += f"**Progress:** {progress_bar} {progress_percentage}%\n"

            if estimated_time:
                content += f"**ETA:** {estimated_time}\n"

            # Send status update
            result = self.client.send_message(
                message_type="stream",
                to=agent["stream_name"],
                topic="Status",
                content=content,
            )

            # Update agent status in registry
            agent_status = {
                "working": AgentStatus.WORKING,
                "waiting": AgentStatus.WAITING,
                "blocked": AgentStatus.BLOCKED,
                "idle": AgentStatus.IDLE,
            }.get(status, AgentStatus.IDLE)

            self.registry.update_agent_status(agent_id, agent_status, current_task)

            if result.get("result") == "success":
                return {"status": "success", "message": "Status update sent"}

            return {
                "status": "error",
                "error": result.get("msg", "Failed to send status"),
            }

        except Exception as e:
            logger.error(f"Failed to send agent status: {e}")
            return {"status": "error", "error": str(e)}

    def handle_user_response(
        self, request_id: str, response: str, user_email: str | None = None
    ) -> dict[str, Any]:
        """Handle user response to an input request."""
        try:
            # Get the pending request
            request = self.db.get_pending_request(request_id)
            if not request:
                return {
                    "status": "error",
                    "error": "Request not found or already answered",
                }

            # Save response
            success = self.db.save_user_response(request_id, response, user_email)

            if success:
                # Parse response if it was a numbered option
                options = request.get("options")
                if options:
                    try:
                        # Check if response is a number
                        selection = int(response.strip())
                        if 1 <= selection <= len(options):
                            parsed_response = options[selection - 1]
                        else:
                            parsed_response = response
                    except ValueError:
                        parsed_response = response
                else:
                    parsed_response = response

                return {
                    "status": "success",
                    "response": parsed_response,
                    "request_id": request_id,
                }

            return {"status": "error", "error": "Failed to save response"}

        except Exception as e:
            logger.error(f"Failed to handle user response: {e}")
            return {"status": "error", "error": str(e)}
