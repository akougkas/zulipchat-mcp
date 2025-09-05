"""Zulip API client wrapper for MCP integration."""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from zulip import Client

from .cache import cache_decorator, stream_cache, user_cache
from .config import ConfigManager


class ZulipMessage(BaseModel):
    """Zulip message model."""

    id: int
    sender_full_name: str
    sender_email: str
    timestamp: int
    content: str
    stream_name: str | None = None
    subject: str | None = None
    type: str
    reactions: list[dict[str, Any]] = []


class ZulipStream(BaseModel):
    """Zulip stream model."""

    stream_id: int
    name: str
    description: str
    is_private: bool
    subscribers: list[str] = []


class ZulipUser(BaseModel):
    """Zulip user model."""

    user_id: int
    full_name: str
    email: str
    is_active: bool
    is_bot: bool
    avatar_url: str | None = None


class ZulipClientWrapper:
    """Wrapper around Zulip client with enhanced functionality and dual identity support."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        use_bot_identity: bool = False,
    ):
        """Initialize Zulip client wrapper.

        Args:
            config_manager: Configuration manager instance
            use_bot_identity: If True, use bot credentials when available
        """
        self.config_manager = config_manager or ConfigManager()
        self.use_bot_identity = use_bot_identity

        if not self.config_manager.validate_config():
            raise ValueError("Invalid Zulip configuration")

        # Check if bot identity is requested and available
        if use_bot_identity and self.config_manager.has_bot_credentials():
            client_config = self.config_manager.get_zulip_client_config(use_bot=True)
            self.identity = "bot"
            self.identity_name = self.config_manager.config.bot_name
        else:
            client_config = self.config_manager.get_zulip_client_config(use_bot=False)
            self.identity = "user"
            self.identity_name = client_config["email"].split("@")[0]

        self.client = Client(
            email=client_config["email"],
            api_key=client_config["api_key"],
            site=client_config["site"],
        )
        self.current_email = client_config["email"]

    def send_message(
        self,
        message_type: str,
        to: str | list[str],
        content: str,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Send a message to a stream or user."""
        request: dict[str, Any] = {"type": message_type, "content": content}

        if message_type == "stream":
            request["to"] = to if isinstance(to, str) else to[0]
            if topic:
                request["topic"] = topic
        else:  # private message
            request["to"] = to if isinstance(to, list) else [to]

        return self.client.send_message(request)

    def get_messages(
        self,
        anchor: str = "newest",
        num_before: int = 100,
        num_after: int = 0,
        narrow: list[dict[str, str]] | None = None,
    ) -> list[ZulipMessage]:
        """Get messages with optional filtering."""
        request = {
            "anchor": anchor,
            "num_before": num_before,
            "num_after": num_after,
            "narrow": narrow or [],
        }

        response = self.client.get_messages(request)
        if response["result"] == "success":
            return [
                ZulipMessage(
                    id=msg["id"],
                    sender_full_name=msg["sender_full_name"],
                    sender_email=msg["sender_email"],
                    timestamp=msg["timestamp"],
                    content=msg["content"],
                    stream_name=msg.get("display_recipient"),
                    subject=msg.get("subject"),
                    type=msg["type"],
                    reactions=msg.get("reactions", []),
                )
                for msg in response["messages"]
            ]
        return []

    @cache_decorator(ttl=300, key_prefix="messages_")
    def get_messages_from_stream(
        self,
        stream_name: str | None = None,
        topic: str | None = None,
        hours_back: int = 24,
        limit: int = 100,
    ) -> list[ZulipMessage]:
        """Get messages from a specific stream."""
        narrow = []
        if stream_name:
            narrow.append({"operator": "stream", "operand": stream_name})
        if topic:
            narrow.append({"operator": "topic", "operand": topic})

        # Add time filter for recent messages
        since_time = datetime.now() - timedelta(hours=hours_back)
        narrow.append({"operator": "search", "operand": f"sent_after:{since_time.strftime('%Y-%m-%d')}"})

        return self.get_messages(narrow=narrow, num_before=limit)

    def search_messages(
        self, query: str, num_results: int = 50
    ) -> list[ZulipMessage]:
        """Search messages by content."""
        narrow = [{"operator": "search", "operand": query}]
        return self.get_messages(narrow=narrow, num_before=num_results)

    def clear_stream_cache(self) -> None:
        """Clear the stream cache."""
        stream_cache.clear()

    def get_streams(self, include_subscribed: bool = True, force_fresh: bool = False) -> list[ZulipStream]:
        """Get list of streams."""
        if not force_fresh:
            # Check cache first
            cached_streams = stream_cache.get_streams()
            if cached_streams is not None:
                return cached_streams

        # Fetch from API and cache
        response = self.client.get_streams(include_subscribed=include_subscribed)
        if response["result"] == "success":
            streams = [
                ZulipStream(
                    stream_id=stream["stream_id"],
                    name=stream["name"],
                    description=stream["description"],
                    is_private=stream.get("invite_only", False),
                )
                for stream in response["streams"]
            ]
            stream_cache.set_streams(streams)
            return streams
        return []

    def get_users(self) -> list[ZulipUser]:
        """Get list of users."""
        # Check cache first
        cached_users = user_cache.get_users()
        if cached_users is not None:
            return cached_users

        # Fetch from API and cache
        response = self.client.get_users()
        if response["result"] == "success":
            users = [
                ZulipUser(
                    user_id=user["user_id"],
                    full_name=user["full_name"],
                    email=user["email"],
                    is_active=user["is_active"],
                    is_bot=user["is_bot"],
                    avatar_url=user.get("avatar_url"),
                )
                for user in response["members"]
            ]
            user_cache.set_users(users)
            return users
        return []

    def add_reaction(self, message_id: int, emoji_name: str) -> dict[str, Any]:
        """Add reaction to a message."""
        return self.client.add_reaction(
            {"message_id": message_id, "emoji_name": emoji_name}
        )

    def edit_message(
        self, message_id: int, content: str | None = None, topic: str | None = None
    ) -> dict[str, Any]:
        """Edit a message."""
        request: dict[str, Any] = {"message_id": message_id}
        if content:
            request["content"] = content
        if topic:
            request["topic"] = topic

        return self.client.update_message(request)

    def get_daily_summary(
        self, streams: list[str] | None = None, hours_back: int = 24
    ) -> dict[str, Any]:
        """Get daily message summary."""
        if not streams:
            # Get all subscribed streams
            all_streams = self.get_streams()
            streams = [s.name for s in all_streams if not s.is_private]

        summary: dict[str, Any] = {
            "total_messages": 0,
            "streams": {},
            "top_senders": {},
            "time_range": f"Last {hours_back} hours",
        }

        for stream_name in streams:
            messages = self.get_messages_from_stream(stream_name, hours_back=hours_back)
            summary["streams"][stream_name] = {
                "message_count": len(messages),
                "topics": {},
            }

            for msg in messages:
                summary["total_messages"] += 1

                # Count by sender
                sender = msg.sender_full_name
                summary["top_senders"][sender] = (
                    summary["top_senders"].get(sender, 0) + 1
                )

                # Count by topic
                if msg.subject:
                    topic_count = summary["streams"][stream_name]["topics"].get(
                        msg.subject, 0
                    )
                    summary["streams"][stream_name]["topics"][msg.subject] = (
                        topic_count + 1
                    )

        # Sort top senders
        summary["top_senders"] = dict(
            sorted(summary["top_senders"].items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
        )

        return summary
