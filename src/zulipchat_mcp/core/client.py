"""Zulip API client wrapper for MCP integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from zulip import Client

from ..config import ConfigManager
from .cache import cache_decorator, stream_cache, user_cache


@dataclass
class ZulipMessage:
    """Represents a Zulip message."""
    id: int
    sender_full_name: str
    sender_email: str
    timestamp: int
    content: str
    type: str
    stream_name: str = ""
    subject: str = ""


@dataclass
class ZulipStream:
    """Represents a Zulip stream."""
    id: int
    name: str
    description: str
    invite_only: bool = False


@dataclass  
class ZulipUser:
    """Represents a Zulip user."""
    id: int
    full_name: str
    email: str
    is_active: bool = True


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
            self.identity_name = self.config_manager.config.bot_name or "Bot"
        else:
            client_config = self.config_manager.get_zulip_client_config(use_bot=False)
            self.identity = "user"
            email = client_config.get("email")
            self.identity_name = email.split("@")[0] if email else "User"

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

    def get_messages_raw(
        self,
        anchor: str = "newest",
        num_before: int = 100,
        num_after: int = 0,
        narrow: list[dict[str, str]] | None = None,
        include_anchor: bool = True,
        client_gravatar: bool = True,
        apply_markdown: bool = True,
    ) -> dict[str, Any]:
        """Get raw messages response from Zulip API."""
        request = {
            "anchor": anchor,
            "num_before": num_before,
            "num_after": num_after,
            "narrow": narrow or [],
            "include_anchor": include_anchor,
            "client_gravatar": client_gravatar,
            "apply_markdown": apply_markdown,
        }

        return self.client.get_messages(request)

    @cache_decorator(ttl=300, key_prefix="messages_")
    def get_messages_from_stream(
        self,
        stream_name: str | None = None,
        topic: str | None = None,
        hours_back: int = 24,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get messages from a specific stream."""
        narrow = []
        if stream_name:
            narrow.append({"operator": "stream", "operand": stream_name})
        if topic:
            narrow.append({"operator": "topic", "operand": topic})

        # Add time filter for recent messages
        since_time = datetime.now() - timedelta(hours=hours_back)
        narrow.append(
            {
                "operator": "search",
                "operand": f"sent_after:{since_time.strftime('%Y-%m-%d')}",
            }
        )

        return self.get_messages_raw(
            narrow=narrow,
            num_before=limit,
            include_anchor=True,
            client_gravatar=True,
            apply_markdown=True,
        )

    def search_messages(self, query: str, num_results: int = 50) -> dict[str, Any]:
        """Search messages by content."""
        narrow = [{"operator": "search", "operand": query}]
        try:
            return self.get_messages_raw(
                narrow=narrow,
                num_before=num_results,
                include_anchor=True,
                client_gravatar=True,
                apply_markdown=True,
            )
        except Exception:
            # Fallback: try without narrow if search fails
            return self.get_messages_raw(
                num_before=num_results,
                include_anchor=True,
                client_gravatar=True,
                apply_markdown=True,
            )

    def get_streams(
        self, include_subscribed: bool = True, force_fresh: bool = False
    ) -> dict[str, Any]:
        """Get list of streams."""
        if not force_fresh:
            # Check cache first
            cached_streams = stream_cache.get_streams()
            if cached_streams is not None:
                return {"result": "success", "streams": cached_streams}

        # Fetch from API
        response = self.client.get_streams(include_subscribed=include_subscribed)
        if response["result"] == "success":
            stream_cache.set_streams(response["streams"])
        return response

    def get_users(self) -> dict[str, Any]:
        """Get list of users."""
        # Check cache first
        cached_users = user_cache.get_users()
        if cached_users is not None:
            return {"result": "success", "members": cached_users}

        # Fetch from API
        response = self.client.get_users()
        if response["result"] == "success":
            user_cache.set_users(response["members"])
        return response

    def add_reaction(self, message_id: int, emoji_name: str) -> dict[str, Any]:
        """Add reaction to a message."""
        return self.client.add_reaction(
            {"message_id": message_id, "emoji_name": emoji_name}
        )

    def remove_reaction(self, message_id: int, emoji_name: str) -> dict[str, Any]:
        """Remove reaction from a message."""
        return self.client.remove_reaction(
            {"message_id": message_id, "emoji_name": emoji_name}
        )

    def edit_message(
        self,
        message_id: int,
        content: str | None = None,
        topic: str | None = None,
        propagate_mode: str = "change_one",
        send_notification_to_old_thread: bool = False,
        send_notification_to_new_thread: bool = True,
        stream_id: int | None = None,
    ) -> dict[str, Any]:
        """Edit a message."""
        request: dict[str, Any] = {"message_id": message_id}
        if content:
            request["content"] = content
        if topic:
            request["topic"] = topic
        if stream_id:
            request["stream_id"] = stream_id
        request["propagate_mode"] = propagate_mode
        request["send_notification_to_old_thread"] = send_notification_to_old_thread
        request["send_notification_to_new_thread"] = send_notification_to_new_thread

        return self.client.update_message(request)

    def get_daily_summary(
        self, streams: list[str] | None = None, hours_back: int = 24
    ) -> dict[str, Any]:
        """Get daily message summary."""
        if not streams:
            # Get all subscribed streams
            streams_response = self.get_streams()
            if streams_response["result"] == "success":
                streams = [
                    s["name"]
                    for s in streams_response["streams"]
                    if not s.get("invite_only", False)
                ]
            else:
                return {"error": "Failed to fetch streams"}

        summary: dict[str, Any] = {
            "total_messages": 0,
            "streams": {},
            "top_senders": {},
            "time_range": f"Last {hours_back} hours",
        }

        for stream_name in streams:
            messages_response = self.get_messages_from_stream(
                stream_name, hours_back=hours_back
            )

            if messages_response.get("result") != "success":
                continue

            messages = messages_response.get("messages", [])
            summary["streams"][stream_name] = {
                "message_count": len(messages),
                "topics": {},
            }

            for msg in messages:
                summary["total_messages"] += 1

                # Count by sender
                sender = msg.get("sender_full_name", "Unknown")
                summary["top_senders"][sender] = (
                    summary["top_senders"].get(sender, 0) + 1
                )

                # Count by topic
                topic = msg.get("subject")
                if topic:
                    topic_count = summary["streams"][stream_name]["topics"].get(
                        topic, 0
                    )
                    summary["streams"][stream_name]["topics"][topic] = topic_count + 1

        # Sort top senders
        summary["top_senders"] = dict(
            sorted(summary["top_senders"].items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
        )

        return summary


# Export list for compatibility wrapper
__all__ = [
    "ZulipClientWrapper",
    "ZulipMessage", 
    "ZulipStream",
    "ZulipUser",
]
