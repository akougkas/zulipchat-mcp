"""Smart notification system for Zulip with priority-based routing."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .async_client import AsyncZulipClient
from .config import ZulipConfig


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SmartNotification(BaseModel):
    """Smart notification with priority and routing information."""
    priority: NotificationPriority
    recipients: list[str]
    content: str
    channels: list[str] = ["zulip"]  # zulip, email, slack placeholders
    retry_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class SmartNotificationSystem:
    """Simple notification system with basic priority handling."""

    def __init__(self, config: ZulipConfig) -> None:
        """Initialize notification system.

        Args:
            config: Zulip configuration
        """
        self.config = config

    async def notify(
        self,
        recipients: list[str],
        content: str,
        priority: NotificationPriority
    ) -> dict[str, Any]:
        """Send notification based on priority.

        Args:
            recipients: List of recipient emails
            content: Notification content
            priority: Notification priority level

        Returns:
            Notification result
        """
        if priority == NotificationPriority.URGENT:
            return await self._send_urgent_notification(recipients, content)
        else:
            # Basic batching for non-urgent notifications
            return await self._send_batch_notification(recipients, content)



    async def _send_urgent_notification(self, recipients: list[str], content: str) -> dict[str, Any]:
        """Send urgent notification with @mention immediately."""
        async with AsyncZulipClient(self.config) as client:
            # Create @mention content
            mentions = " ".join([f"@**{recipient}**" for recipient in recipients])
            full_content = f"🚨 **URGENT**: {content}\n\n{mentions}"

            # Send as direct message to each recipient
            results = []
            for recipient in recipients:
                try:
                    result = await client.send_message_async(
                        message_type="private",
                        to=recipient,
                        content=full_content
                    )
                    results.append({"recipient": recipient, "status": "sent", "result": result})
                except Exception as e:
                    results.append({"recipient": recipient, "status": "failed", "error": str(e)})

            return {
                "priority": "urgent",
                "type": "urgent",
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

    async def _send_batch_notification(self, recipients: list[str], content: str) -> dict[str, Any]:
        """Send basic notification to recipients."""
        async with AsyncZulipClient(self.config) as client:
            results = []
            for recipient in recipients:
                try:
                    result = await client.send_message_async(
                        message_type="private",
                        to=recipient,
                        content=content
                    )
                    results.append({"recipient": recipient, "status": "sent", "result": result})
                except Exception as e:
                    results.append({"recipient": recipient, "status": "failed", "error": str(e)})

            return {
                "priority": "normal",
                "type": "batch",
                "results": results,
                "timestamp": datetime.now().isoformat()
            }


async def smart_notify(
    config: ZulipConfig,
    recipients: list[str],
    content: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM
) -> dict[str, Any]:
    """Helper function to create and send a smart notification.
    
    Args:
        config: Zulip configuration
        recipients: List of recipient emails
        content: Notification content
        priority: Notification priority level
        
    Returns:
        Notification result
    """
    system = SmartNotificationSystem(config)
    return await system.notify(recipients, content, priority)
