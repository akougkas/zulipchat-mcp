"""Simple Zulip API client wrapper for MCP integration.

Minimal wrapper around the Zulip client with dual identity support and basic caching.
"""

from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass

from zulip import Client

from .config import ConfigManager


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


class SimpleCache:
    """Simple in-memory cache with TTL."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now().timestamp() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self.cache[key] = (value, datetime.now().timestamp())


class ZulipClientWrapper:
    """Simple wrapper around Zulip client with dual identity support."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        use_bot_identity: bool = False,
    ):
        self.config_manager = config_manager or ConfigManager()
        self.use_bot_identity = use_bot_identity

        if not self.config_manager.validate_config():
            raise ValueError("Invalid Zulip configuration")

        # Check bot identity availability
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
        self.base_url = client_config["site"].rstrip('/') if client_config["site"] else ""

        # Simple caches
        self._users_cache = SimpleCache(ttl_seconds=900)  # 15 minutes
        self._streams_cache = SimpleCache(ttl_seconds=600)  # 10 minutes

    def send_message(
        self,
        message_type: str,
        to: str | list[str],
        content: str,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Send a message to a stream or user."""
        request = {"type": message_type, "content": content}

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

    def get_users(self) -> dict[str, Any]:
        """Get list of users with caching."""
        cached = self._users_cache.get("users_list")
        if cached is not None:
            return {"result": "success", "members": cached}

        response = self.client.get_users()
        if response["result"] == "success":
            self._users_cache.set("users_list", response["members"])
        return response

    def get_streams(self, include_subscribed: bool = True) -> dict[str, Any]:
        """Get list of streams with caching."""
        cache_key = f"streams_{include_subscribed}"
        cached = self._streams_cache.get(cache_key)
        if cached is not None:
            return {"result": "success", "streams": cached}

        response = self.client.get_streams(include_subscribed=include_subscribed)
        if response["result"] == "success":
            self._streams_cache.set(cache_key, response["streams"])
        return response

    def get_stream_id(self, stream: str) -> dict[str, Any]:
        """Get stream ID by name."""
        return self.client.get_stream_id(stream)

    def get_stream_topics(self, stream_id: int) -> dict[str, Any]:
        """Get recent topics for a stream."""
        return self.client.get_stream_topics(stream_id)

    def get_subscribers(self, stream_id: int) -> dict[str, Any]:
        """Get subscribers for a stream."""
        return self.client.get_subscribers(stream_id)

    def add_reaction(self, message_id: int, emoji_name: str) -> dict[str, Any]:
        """Add reaction to a message."""
        return self.client.add_reaction({"message_id": message_id, "emoji_name": emoji_name})

    def remove_reaction(self, message_id: int, emoji_name: str) -> dict[str, Any]:
        """Remove reaction from a message."""
        return self.client.remove_reaction({"message_id": message_id, "emoji_name": emoji_name})

    def edit_message(
        self,
        message_id: int,
        content: str | None = None,
        topic: str | None = None,
        propagate_mode: str = "change_one",
    ) -> dict[str, Any]:
        """Edit a message."""
        request = {"message_id": message_id, "propagate_mode": propagate_mode}
        if content:
            request["content"] = content
        if topic:
            request["topic"] = topic

        return self.client.update_message(request)

    # Stream management
    def add_subscriptions(self, subscriptions: list[dict[str, Any]], **kwargs) -> dict[str, Any]:
        """Subscribe to streams."""
        return self.client.add_subscriptions(streams=subscriptions, **kwargs)

    def remove_subscriptions(self, subscriptions: list[str]) -> dict[str, Any]:
        """Unsubscribe from streams."""
        return self.client.remove_subscriptions(subscriptions=subscriptions)

    def delete_stream(self, stream_id: int) -> dict[str, Any]:
        """Delete a stream."""
        return self.client.call_endpoint(f"streams/{stream_id}", method="DELETE", request={})

    # Event system
    def register(self, **kwargs: Any) -> dict[str, Any]:
        """Register an event queue."""
        return self.client.register(**kwargs)

    def get_events(self, **kwargs: Any) -> dict[str, Any]:
        """Get events from a queue."""
        return self.client.get_events(**kwargs)

    def deregister(self, queue_id: str) -> dict[str, Any]:
        """Delete an event queue."""
        return self.client.call_endpoint("events", method="DELETE", request={"queue_id": queue_id})

    # User management
    def get_user_by_email(self, email: str, include_custom_profile_fields: bool = False) -> dict[str, Any]:
        """Get user by email."""
        return self.client.call_endpoint(
            f"users/{email}",
            method="GET",
            request={"include_custom_profile_fields": include_custom_profile_fields},
        )

    def get_user_by_id(self, user_id: int, include_custom_profile_fields: bool = False) -> dict[str, Any]:
        """Get user by ID."""
        return self.client.call_endpoint(
            f"users/{user_id}",
            method="GET",
            request={"include_custom_profile_fields": include_custom_profile_fields},
        )

    def update_presence(self, status: str, ping_only: bool = False) -> dict[str, Any]:
        """Update presence status."""
        return self.client.call_endpoint(
            "users/me/presence",
            method="POST",
            request={"status": status, "ping_only": ping_only, "new_user_input": True},
        )

    # File operations
    def upload_file(self, file_content: bytes, filename: str) -> dict[str, Any]:
        """Upload a file to Zulip."""
        import io
        file_obj = io.BytesIO(file_content)
        file_obj.name = filename

        try:
            return self.client.upload_file(file_obj)
        except Exception:
            # Fallback to direct API call
            import requests
            import base64

            url = f"{self.base_url}/api/v1/user_uploads"
            files = {'file': (filename, file_content)}

            auth_string = f"{self.client.email}:{self.client.api_key}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            headers = {'Authorization': f'Basic {auth_bytes}'}

            response = requests.post(url, files=files, headers=headers)
            if response.status_code == 200:
                return {"result": "success", **response.json()}
            else:
                return {"result": "error", "msg": f"Upload failed: {response.text}"}

    # Additional client methods for complete functionality
    def get_message(self, message_id: int) -> dict[str, Any]:
        """Fetch a single message by ID."""
        return self.client.call_endpoint(f"messages/{message_id}", method="GET", request={})

    def update_message_flags(self, messages: list[int], op: str, flag: str) -> dict[str, Any]:
        """Add/remove a flag on a list of messages."""
        payload = {"messages": messages, "op": op, "flag": flag}
        return self.client.call_endpoint("messages/flags", method="POST", request=payload)

    def get_subscriptions(self) -> dict[str, Any]:
        """Get user's stream subscriptions."""
        return self.client.get_subscriptions()

    def update_subscription_settings(self, subscriptions: list[dict[str, Any]]) -> dict[str, Any]:
        """Update subscription settings."""
        return self.client.call_endpoint(
            "users/me/subscriptions/properties",
            method="PATCH",
            request={"subscription_data": subscriptions},
        )

    def mark_topic_as_read(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        """Mark all messages in a topic as read."""
        return self.client.call_endpoint(
            "mark_topic_as_read",
            method="POST",
            request={"stream_id": stream_id, "topic_name": topic_name},
        )

    def mute_topic(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        """Mute a topic."""
        return self.client.call_endpoint(
            "users/me/muted_topics",
            method="PATCH",
            request={"op": "add", "stream_id": stream_id, "topic": topic_name},
        )

    def unmute_topic(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        """Unmute a topic."""
        return self.client.call_endpoint(
            "users/me/muted_topics",
            method="PATCH",
            request={"op": "remove", "stream_id": stream_id, "topic": topic_name},
        )

    def delete_topic(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        """Delete a topic."""
        try:
            return self.client.call_endpoint(
                f"streams/{stream_id}/delete_topic",
                method="POST",
                request={"topic_name": topic_name},
            )
        except Exception:
            return {"result": "error", "msg": "Failed to delete topic"}

    def update_user(self, user_id: int, **updates: Any) -> dict[str, Any]:
        """Update user information."""
        return self.client.call_endpoint(
            f"users/{user_id}", method="PATCH", request=updates
        )

    # Utility methods
    def get_daily_summary(self, streams: list[str] | None = None, hours_back: int = 24) -> dict[str, Any]:
        """Get daily message summary."""
        if not streams:
            streams_response = self.get_streams()
            if streams_response["result"] == "success":
                streams = [s["name"] for s in streams_response["streams"]]

        summary = {
            "total_messages": 0,
            "streams": {},
            "top_senders": {},
            "time_range": f"Last {hours_back} hours",
        }

        since_time = datetime.now() - timedelta(hours=hours_back)

        for stream_name in streams or []:
            narrow = [
                {"operator": "stream", "operand": stream_name},
                {"operator": "search", "operand": f"after:{since_time.isoformat()}"},
            ]

            messages_response = self.get_messages_raw(narrow=narrow, num_before=100)

            if messages_response.get("result") != "success":
                continue

            messages = messages_response.get("messages", [])
            summary["streams"][stream_name] = {"message_count": len(messages), "topics": {}}
            summary["total_messages"] += len(messages)

            for msg in messages:
                sender = msg.get("sender_full_name", "Unknown")
                summary["top_senders"][sender] = summary["top_senders"].get(sender, 0) + 1

                topic = msg.get("subject")
                if topic:
                    summary["streams"][stream_name]["topics"][topic] = (
                        summary["streams"][stream_name]["topics"].get(topic, 0) + 1
                    )

        # Sort top senders
        summary["top_senders"] = dict(
            sorted(summary["top_senders"].items(), key=lambda x: x[1], reverse=True)[:10]
        )

        return summary