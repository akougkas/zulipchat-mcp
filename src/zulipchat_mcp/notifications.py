"""Smart notification system for Zulip with priority-based routing."""

import asyncio
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

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
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.now()
        super().__init__(**data)


class SmartNotificationSystem:
    """Smart notification system with priority-based routing."""

    def __init__(self, config: ZulipConfig) -> None:
        """Initialize notification system.
        
        Args:
            config: Zulip configuration
        """
        self.config = config
        self.pending_batches: dict[str, list[SmartNotification]] = {}
        self.user_preferences: dict[str, dict] = {}
        self._batch_task: asyncio.Task | None = None

    async def notify(
        self,
        recipients: list[str],
        content: str,
        priority: NotificationPriority
    ) -> dict[str, any]:
        """Route notification based on priority.
        
        Args:
            recipients: List of recipient emails
            content: Notification content
            priority: Notification priority level
            
        Returns:
            Notification result
        """
        notification = SmartNotification(
            priority=priority,
            recipients=recipients,
            content=content
        )

        if priority == NotificationPriority.URGENT:
            return await self._send_urgent_notification(notification)
        elif priority == NotificationPriority.HIGH:
            return await self._send_high_priority_notification(notification)
        elif priority == NotificationPriority.MEDIUM:
            return await self._queue_for_batch(notification, delay_minutes=15)
        else:  # LOW priority
            return await self._queue_for_daily_digest(notification)

    async def batch_notify(self, notifications: list[SmartNotification]) -> list[dict[str, any]]:
        """Send multiple notifications efficiently.
        
        Args:
            notifications: List of notifications to send
            
        Returns:
            List of notification results
        """
        results = []

        # Group by priority for efficient processing
        urgent = [n for n in notifications if n.priority == NotificationPriority.URGENT]
        high = [n for n in notifications if n.priority == NotificationPriority.HIGH]
        medium = [n for n in notifications if n.priority == NotificationPriority.MEDIUM]
        low = [n for n in notifications if n.priority == NotificationPriority.LOW]

        # Process urgent immediately
        for notification in urgent:
            result = await self._send_urgent_notification(notification)
            results.append(result)

        # Process high priority
        for notification in high:
            result = await self._send_high_priority_notification(notification)
            results.append(result)

        # Batch medium priority
        if medium:
            result = await self._send_batch_notifications(medium)
            results.extend(result)

        # Queue low priority for digest
        for notification in low:
            result = await self._queue_for_daily_digest(notification)
            results.append(result)

        return results

    async def create_digest(
        self,
        user: str,
        notifications: list[SmartNotification]
    ) -> str:
        """Group notifications into a digest format.
        
        Args:
            user: User email
            notifications: List of notifications for the user
            
        Returns:
            Formatted digest content
        """
        if not notifications:
            return ""

        digest_content = f"# Daily Digest for {user}\n\n"
        digest_content += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

        # Group by priority
        priority_groups = {
            NotificationPriority.HIGH: [],
            NotificationPriority.MEDIUM: [],
            NotificationPriority.LOW: []
        }

        for notification in notifications:
            if notification.priority in priority_groups:
                priority_groups[notification.priority].append(notification)

        # Format by priority
        for priority, group_notifications in priority_groups.items():
            if group_notifications:
                digest_content += f"## {priority.value.title()} Priority ({len(group_notifications)} items)\n\n"
                for notification in group_notifications:
                    time_str = notification.created_at.strftime('%H:%M')
                    digest_content += f"- **{time_str}**: {notification.content}\n"
                digest_content += "\n"

        return digest_content

    def should_notify_now(
        self,
        notification: SmartNotification,
        user_preferences: dict | None = None
    ) -> bool:
        """Decide if notification should be sent immediately.
        
        Args:
            notification: The notification to check
            user_preferences: User notification preferences
            
        Returns:
            True if should notify immediately
        """
        if not user_preferences:
            user_preferences = {}

        # Always notify urgent immediately
        if notification.priority == NotificationPriority.URGENT:
            return True

        # Check user quiet hours
        quiet_start = user_preferences.get('quiet_hours_start', 22)  # 10 PM
        quiet_end = user_preferences.get('quiet_hours_end', 8)       # 8 AM
        current_hour = datetime.now().hour

        if quiet_start > quiet_end:  # Crosses midnight
            in_quiet_hours = current_hour >= quiet_start or current_hour < quiet_end
        else:
            in_quiet_hours = quiet_start <= current_hour < quiet_end

        # During quiet hours, only urgent notifications
        if in_quiet_hours and notification.priority != NotificationPriority.URGENT:
            return False

        # Check frequency limits
        max_per_hour = user_preferences.get('max_notifications_per_hour', 10)
        # In a real implementation, you'd track notification history

        return True

    async def _send_urgent_notification(self, notification: SmartNotification) -> dict[str, any]:
        """Send urgent notification with @mention immediately."""
        async with AsyncZulipClient(self.config) as client:
            # Create @mention content
            mentions = " ".join([f"@**{recipient}**" for recipient in notification.recipients])
            content = f"🚨 **URGENT**: {notification.content}\n\n{mentions}"

            # Send as direct message to each recipient
            results = []
            for recipient in notification.recipients:
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
                "priority": notification.priority.value,
                "type": "urgent",
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

    async def _send_high_priority_notification(self, notification: SmartNotification) -> dict[str, any]:
        """Send high priority notification within 5 minutes."""
        # For now, send immediately but could be queued with 5-minute delay
        async with AsyncZulipClient(self.config) as client:
            content = f"⚠️ **High Priority**: {notification.content}"

            results = []
            for recipient in notification.recipients:
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
                "priority": notification.priority.value,
                "type": "high_priority",
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

    async def _queue_for_batch(self, notification: SmartNotification, delay_minutes: int = 15) -> dict[str, any]:
        """Queue notification for batch sending."""
        batch_key = f"batch_{delay_minutes}min"

        if batch_key not in self.pending_batches:
            self.pending_batches[batch_key] = []

        self.pending_batches[batch_key].append(notification)

        # Start batch processing task if not already running
        if not self._batch_task or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._process_batch(batch_key, delay_minutes))

        return {
            "priority": notification.priority.value,
            "type": "queued_for_batch",
            "batch_key": batch_key,
            "delay_minutes": delay_minutes,
            "timestamp": datetime.now().isoformat()
        }

    async def _queue_for_daily_digest(self, notification: SmartNotification) -> dict[str, any]:
        """Queue notification for daily digest."""
        digest_key = "daily_digest"

        if digest_key not in self.pending_batches:
            self.pending_batches[digest_key] = []

        self.pending_batches[digest_key].append(notification)

        return {
            "priority": notification.priority.value,
            "type": "queued_for_digest",
            "timestamp": datetime.now().isoformat()
        }

    async def _send_batch_notifications(self, notifications: list[SmartNotification]) -> list[dict[str, any]]:
        """Send a batch of medium priority notifications."""
        async with AsyncZulipClient(self.config) as client:
            results = []

            # Group notifications by recipient for efficiency
            recipient_notifications = {}
            for notification in notifications:
                for recipient in notification.recipients:
                    if recipient not in recipient_notifications:
                        recipient_notifications[recipient] = []
                    recipient_notifications[recipient].append(notification)

            # Send combined message to each recipient
            for recipient, recipient_notifs in recipient_notifications.items():
                try:
                    if len(recipient_notifs) == 1:
                        content = f"📋 {recipient_notifs[0].content}"
                    else:
                        content = f"📋 **You have {len(recipient_notifs)} notifications:**\n\n"
                        for i, notif in enumerate(recipient_notifs, 1):
                            content += f"{i}. {notif.content}\n"

                    result = await client.send_message_async(
                        message_type="private",
                        to=recipient,
                        content=content
                    )
                    results.append({
                        "recipient": recipient,
                        "status": "sent",
                        "notification_count": len(recipient_notifs),
                        "result": result
                    })
                except Exception as e:
                    results.append({
                        "recipient": recipient,
                        "status": "failed",
                        "notification_count": len(recipient_notifs),
                        "error": str(e)
                    })

            return results

    async def _process_batch(self, batch_key: str, delay_minutes: int) -> None:
        """Process batch notifications after delay."""
        await asyncio.sleep(delay_minutes * 60)  # Convert to seconds

        if batch_key in self.pending_batches and self.pending_batches[batch_key]:
            notifications = self.pending_batches[batch_key]
            self.pending_batches[batch_key] = []  # Clear the batch

            await self._send_batch_notifications(notifications)


async def smart_notify(
    config: ZulipConfig,
    recipients: list[str],
    content: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM
) -> dict[str, any]:
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
