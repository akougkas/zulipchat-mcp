"""Message scheduler for Zulip using native scheduled messages API."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ..config import ZulipConfig


class ScheduledMessage(BaseModel):
    """Scheduled message data model."""

    content: str = Field(..., description="Message content")
    scheduled_time: datetime = Field(..., description="When to send the message")
    message_type: str = Field(..., description="Message type: 'stream' or 'private'")
    recipients: str | list[str] = Field(
        ..., description="Recipients list or stream name"
    )
    topic: str | None = Field(None, description="Topic for stream messages")
    scheduled_id: int | None = Field(None, description="Zulip scheduled message ID")


class MessageScheduler:
    """Message scheduler using Zulip's native scheduled messages API."""

    def __init__(self, config: ZulipConfig) -> None:
        """Initialize message scheduler.

        Args:
            config: Zulip configuration
        """
        self.config = config
        self.base_url = f"{config.site}/api/v1"
        self.auth = (config.email, config.api_key)
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "MessageScheduler":
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            auth=self.auth,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client is initialized."""
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                auth=self.auth,
            )
        return self.client

    def _datetime_to_timestamp(self, dt: datetime) -> int:
        """Convert datetime to UNIX timestamp."""
        return int(dt.timestamp())

    def _timestamp_to_datetime(self, timestamp: int) -> datetime:
        """Convert UNIX timestamp to datetime."""
        return datetime.fromtimestamp(timestamp)

    async def schedule_message(self, message: ScheduledMessage) -> dict[str, Any]:
        """Schedule a message using Zulip's native API.

        Args:
            message: Scheduled message details

        Returns:
            API response with scheduled message ID
        """
        client = self._ensure_client()

        # Prepare data for API
        data = {
            "content": message.content,
            "scheduled_delivery_timestamp": self._datetime_to_timestamp(
                message.scheduled_time
            ),
            "type": message.message_type,
        }

        # Get client for lookups
        from .client import ZulipClientWrapper
        from .config import ConfigManager

        client_wrapper = ZulipClientWrapper(ConfigManager())

        # Set recipients based on message type
        if message.message_type == "stream":
            stream_name = (
                message.recipients
                if isinstance(message.recipients, str)
                else message.recipients[0]
            )
            streams = client_wrapper.get_streams()
            stream_id = next(
                (s.stream_id for s in streams if s.name == stream_name), None
            )

            if not stream_id:
                raise ValueError(f"Stream '{stream_name}' not found.")

            data["to"] = stream_id
            if message.topic:
                data["topic"] = message.topic
        else:  # private message
            recipient_emails = (
                message.recipients
                if isinstance(message.recipients, list)
                else [message.recipients]
            )
            all_users = client_wrapper.get_users()

            user_ids = []
            for email in recipient_emails:
                user_id = next((u.user_id for u in all_users if u.email == email), None)
                if user_id:
                    user_ids.append(user_id)

            if not user_ids:
                raise ValueError("No valid user IDs found for the given emails.")

            data["to"] = json.dumps(user_ids)

        response = await client.post(f"{self.base_url}/scheduled_messages", data=data)
        response.raise_for_status()
        result = response.json()

        # Update message with scheduled ID
        if result.get("result") == "success":
            message.scheduled_id = result.get("scheduled_message_id")

        return result

    async def cancel_scheduled(self, scheduled_id: int) -> dict[str, Any]:
        """Cancel a scheduled message.

        Args:
            scheduled_id: ID of scheduled message to cancel

        Returns:
            API response
        """
        client = self._ensure_client()

        response = await client.delete(
            f"{self.base_url}/scheduled_messages/{scheduled_id}"
        )
        response.raise_for_status()
        return response.json()

    async def list_scheduled(self) -> list[dict[str, Any]]:
        """List all scheduled messages.

        Returns:
            List of scheduled messages
        """
        client = self._ensure_client()

        response = await client.get(f"{self.base_url}/scheduled_messages")
        response.raise_for_status()
        data = response.json()

        if data.get("result") == "success":
            return data.get("scheduled_messages", [])
        return []

    async def update_scheduled(
        self, scheduled_id: int, new_time: datetime
    ) -> dict[str, Any]:
        """Update the scheduled time of a message.

        Args:
            scheduled_id: ID of scheduled message
            new_time: New scheduled time

        Returns:
            API response
        """
        client = self._ensure_client()

        data = {"scheduled_delivery_timestamp": self._datetime_to_timestamp(new_time)}

        response = await client.patch(
            f"{self.base_url}/scheduled_messages/{scheduled_id}", data=data
        )
        response.raise_for_status()
        return response.json()

    async def schedule_recurring(
        self, message: ScheduledMessage, interval: timedelta, count: int = 7
    ) -> list[dict[str, Any]]:
        """Schedule multiple messages at regular intervals.

        Args:
            message: Base message to schedule
            interval: Time interval between messages
            count: Number of messages to schedule

        Returns:
            List of API responses for each scheduled message
        """
        results = []
        current_time = message.scheduled_time

        for _i in range(count):
            # Create a new message for each occurrence
            recurring_message = ScheduledMessage(
                content=message.content,
                scheduled_time=current_time,
                message_type=message.message_type,
                recipients=message.recipients,
                topic=message.topic,
            )

            result = await self.schedule_message(recurring_message)
            results.append(result)

            # Increment time for next occurrence
            current_time += interval

        return results

    async def schedule_reminder(
        self,
        content: str,
        minutes_from_now: int,
        recipients: str | list[str],
        message_type: str = "private",
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Schedule a reminder message.

        Args:
            content: Reminder message content
            minutes_from_now: Minutes from now to send reminder
            recipients: Who to send the reminder to
            message_type: Type of message (private or stream)
            topic: Topic for stream messages

        Returns:
            API response
        """
        scheduled_time = datetime.now() + timedelta(minutes=minutes_from_now)

        reminder = ScheduledMessage(
            content=f"⏰ Reminder: {content}",
            scheduled_time=scheduled_time,
            message_type=message_type,
            recipients=recipients,
            topic=topic,
        )

        return await self.schedule_message(reminder)

    async def schedule_daily_standup(
        self, stream: str, topic: str, time_of_day: str, days_ahead: int = 7
    ) -> list[dict[str, Any]]:
        """Schedule daily standup messages.

        Args:
            stream: Stream to send standup messages
            topic: Topic for standup messages
            time_of_day: Time in HH:MM format (24-hour)
            days_ahead: Number of days to schedule ahead

        Returns:
            List of API responses for each scheduled standup
        """
        # Parse time of day
        try:
            hour, minute = map(int, time_of_day.split(":"))
        except ValueError:
            raise ValueError("time_of_day must be in HH:MM format") from None

        # Create base standup message
        standup_content = """📅 **Daily Standup**

Please share:
• What did you accomplish yesterday?
• What are you working on today?
• Any blockers or help needed?

@**all** - please respond when you can!"""

        results = []

        # Schedule for each day
        for day in range(1, days_ahead + 1):
            # Calculate next occurrence
            tomorrow = datetime.now().replace(
                hour=hour, minute=minute, second=0, microsecond=0
            ) + timedelta(days=day)

            # Skip weekends (Saturday=5, Sunday=6)
            if tomorrow.weekday() >= 5:
                continue

            standup_message = ScheduledMessage(
                content=standup_content,
                scheduled_time=tomorrow,
                message_type="stream",
                recipients=stream,
                topic=topic,
            )

            result = await self.schedule_message(standup_message)
            results.append(result)

        return results

    async def bulk_schedule(
        self, messages: list[ScheduledMessage]
    ) -> list[dict[str, Any]]:
        """Schedule multiple messages in batch.

        Args:
            messages: List of messages to schedule

        Returns:
            List of API responses for each message
        """
        # Use asyncio.gather for concurrent scheduling
        tasks = [self.schedule_message(message) for message in messages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Filter out exceptions and return only successful results
        return [r for r in results if isinstance(r, dict)]

    async def get_scheduled_by_time_range(
        self, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        """Get scheduled messages within a time range.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Filtered list of scheduled messages
        """
        all_scheduled = await self.list_scheduled()

        start_ts = self._datetime_to_timestamp(start_time)
        end_ts = self._datetime_to_timestamp(end_time)

        filtered = []
        for msg in all_scheduled:
            msg_time = msg.get("scheduled_delivery_timestamp", 0)
            if start_ts <= msg_time <= end_ts:
                filtered.append(msg)

        return filtered

    async def cancel_all_scheduled(self) -> list[dict[str, Any]]:
        """Cancel all scheduled messages.

        Returns:
            List of cancellation results
        """
        scheduled_messages = await self.list_scheduled()

        if not scheduled_messages:
            return []

        # Cancel all messages concurrently
        tasks = [
            self.cancel_scheduled(msg["scheduled_message_id"])
            for msg in scheduled_messages
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Filter out exceptions and return only successful results
        return [r for r in results if isinstance(r, dict)]

    async def close(self) -> None:
        """Close the async client."""
        if self.client:
            await self.client.aclose()
            self.client = None


# Convenience functions for easy usage
async def schedule_message(
    config: ZulipConfig, message: ScheduledMessage
) -> dict[str, Any]:
    """Schedule a message using the scheduler.

    Args:
        config: Zulip configuration
        message: Message to schedule

    Returns:
        API response
    """
    async with MessageScheduler(config) as scheduler:
        return await scheduler.schedule_message(message)


async def schedule_reminder(
    config: ZulipConfig,
    content: str,
    minutes_from_now: int,
    recipients: str | list[str],
    message_type: str = "private",
    topic: str | None = None,
) -> dict[str, Any]:
    """Schedule a reminder message.

    Args:
        config: Zulip configuration
        content: Reminder content
        minutes_from_now: Minutes from now
        recipients: Recipients
        message_type: Message type
        topic: Topic for stream messages

    Returns:
        API response
    """
    async with MessageScheduler(config) as scheduler:
        return await scheduler.schedule_reminder(
            content, minutes_from_now, recipients, message_type, topic
        )


async def cancel_scheduled_message(
    config: ZulipConfig, scheduled_id: int
) -> dict[str, Any]:
    """Cancel a scheduled message.

    Args:
        config: Zulip configuration
        scheduled_id: ID of message to cancel

    Returns:
        API response
    """
    async with MessageScheduler(config) as scheduler:
        return await scheduler.cancel_scheduled(scheduled_id)
