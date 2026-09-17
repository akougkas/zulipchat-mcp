"""Zulip API client wrapper for MCP integration."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

from zulip import Client

from ..config import ConfigManager
from .cache import StreamCache, UserCache


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
            self._client_config = self.config_manager.get_zulip_client_config(
                use_bot=True
            )
            self.identity = "bot"
            self.identity_name = self.config_manager.config.bot_name or "Bot"
        else:
            self._client_config = self.config_manager.get_zulip_client_config(
                use_bot=False
            )
            self.identity = "user"
            email = self._client_config.get("email")
            self.identity_name = email.split("@")[0] if email else "User"

        # Lazy loading: client created on first API call
        self._client: Client | None = None
        self._client_lock = Lock()
        self.current_email = self._client_config.get("email")
        site = self._client_config.get("site")
        self._base_url = self._normalize_site_base_url(site) if site else ""
        # Cache data belongs to this authenticated client, never another identity.
        self.user_cache = UserCache()
        self.stream_cache = StreamCache()

    @staticmethod
    def _normalize_site_base_url(base_url: str) -> str:
        """Normalize a site URL so it points to the realm root, not API endpoints."""
        parsed = urlparse(base_url.strip())
        path = parsed.path.rstrip("/")
        if path.endswith("/api"):
            path = path[: -len("/api")]
        elif path.startswith("/api/v") and path[6:].isdigit():
            path = ""
        elif "/api/v" in path:
            path_prefix, _, version_suffix = path.rpartition("/api/v")
            if version_suffix.isdigit():
                path = path_prefix

        if parsed.scheme and parsed.netloc:
            return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

        return path or parsed.netloc or base_url.strip().rstrip("/")

    @property
    def client(self) -> Client:
        """Lazy-loaded Zulip client. Creates connection on first access."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = self._create_client()
        return self._client

    def _create_client(self) -> Client:
        """Create and configure the Zulip client."""
        try:
            if self._client_config.get("config_file"):
                client = Client(
                    email=self._client_config["email"],
                    api_key=self._client_config["api_key"],
                    site=self._client_config["site"],
                    config_file=self._client_config["config_file"],
                    retry_on_errors=False,
                )
                # Backfill properties from loaded client config
                if hasattr(client, "email"):
                    self.current_email = client.email
                    # Update identity name if it was default "User"/Bot
                    if self.identity_name in ("User", "Bot") and self.current_email:
                        self.identity_name = self.current_email.split("@")[0]

                if hasattr(client, "base_url"):
                    self._base_url = self._normalize_site_base_url(client.base_url)

                return client
            else:
                return Client(
                    email=self._client_config["email"],
                    api_key=self._client_config["api_key"],
                    site=self._client_config["site"],
                    retry_on_errors=False,
                )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Zulip: {e}") from e

    @property
    def is_connected(self) -> bool:
        """Check if client connection has been established."""
        return self._client is not None

    @property
    def base_url(self) -> str:
        """Get the base URL for API calls. Ensures client is initialized to load config."""
        if not self._base_url and self._client is None:
            _ = self.client
        return self._base_url

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
            if isinstance(to, list) and len(to) != 1:
                raise ValueError("Stream messages require exactly one stream")
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
        narrow: list[dict[str, Any]] | None = None,
        include_anchor: bool = True,
        client_gravatar: bool = True,
        apply_markdown: bool = True,
        anchor_date: str | None = None,
    ) -> dict[str, Any]:
        """Get raw messages response from Zulip API.

        Args:
            anchor: Message ID or special value ("newest", "oldest", "first_unread", "date")
            anchor_date: ISO 8601 datetime string, required when anchor="date" (Zulip 12.0+)
            num_before: Number of messages before anchor to fetch
            num_after: Number of messages after anchor to fetch
            narrow: List of narrow filter dicts
            include_anchor: Whether to include the anchor message
            client_gravatar: Use client-side gravatar
            apply_markdown: Render markdown in content
        """
        request: dict[str, Any] = {
            "anchor": anchor,
            "num_before": num_before,
            "num_after": num_after,
            "narrow": narrow or [],
            "include_anchor": include_anchor,
            "client_gravatar": client_gravatar,
            "apply_markdown": apply_markdown,
        }

        # Add anchor_date for time-based queries (Zulip 12.0+, feature level 445)
        if anchor == "date" and anchor_date:
            request["anchor_date"] = anchor_date

        return self.client.get_messages(request)

    def get_messages(
        self,
        anchor: str = "newest",
        num_before: int = 50,
        num_after: int = 0,
        narrow: list[dict[str, str]] | None = None,
    ) -> list[ZulipMessage]:
        """Convenience method returning typed ZulipMessage objects.

        This wraps get_messages_raw and maps results to ZulipMessage dataclass
        instances for internal tooling that expects object-style access.
        """
        raw = self.get_messages_raw(
            anchor=anchor,
            num_before=num_before,
            num_after=num_after,
            narrow=narrow,
            include_anchor=True,
            client_gravatar=True,
            apply_markdown=True,
        )
        if raw.get("result") != "success":
            raise RuntimeError(raw.get("msg", "Failed to fetch messages"))
        messages: list[ZulipMessage] = []
        for m in raw.get("messages", []):
            try:
                messages.append(
                    ZulipMessage(
                        id=int(m.get("id", 0)),
                        sender_full_name=m.get("sender_full_name", ""),
                        sender_email=m.get("sender_email", ""),
                        timestamp=int(m.get("timestamp", 0)),
                        content=m.get("content", ""),
                        type=m.get("type", "stream"),
                        stream_name=m.get("display_recipient", ""),
                        subject=m.get("subject", ""),
                    )
                )
            except Exception:
                continue
        return messages

    def get_messages_from_stream(
        self,
        stream_name: str | None = None,
        topic: str | None = None,
        hours_back: int = 24,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get messages from a specific stream within time range.

        Fetches a bounded sample of the newest messages and applies the UTC
        cutoff locally, including on Zulip versions without date anchors.
        """
        if not 1 <= limit <= 1000 or hours_back <= 0:
            raise ValueError(
                "limit must be between 1 and 1000; hours_back must be positive"
            )
        narrow: list[dict[str, Any]] = []
        if stream_name:
            narrow.append({"operator": "stream", "operand": stream_name})
        if topic:
            narrow.append({"operator": "topic", "operand": topic})

        # Calculate cutoff time for time-based filtering
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        result = self.get_messages_raw(
            anchor="newest",
            narrow=narrow,
            num_before=limit,
            num_after=0,
            include_anchor=True,
            client_gravatar=True,
            apply_markdown=True,
        )
        if result.get("result") == "success":
            result = dict(result)
            result["messages"] = [
                message
                for message in result.get("messages", [])
                if message.get("timestamp", 0) >= cutoff_time.timestamp()
            ][-limit:]
        return result

    def search_messages(self, query: str, num_results: int = 50) -> dict[str, Any]:
        """Search messages by content."""
        narrow = [{"operator": "search", "operand": query}]
        return self.get_messages_raw(
            narrow=narrow,
            num_before=num_results,
            include_anchor=True,
            client_gravatar=True,
            apply_markdown=True,
        )

    def get_streams(
        self,
        include_subscribed: bool = True,
        force_fresh: bool = False,
        include_public: bool | None = None,
        include_all_active: bool | None = None,
    ) -> dict[str, Any]:
        """Get list of streams."""
        default_filters = (
            include_subscribed and include_public is None and include_all_active is None
        )
        if not force_fresh and default_filters:
            # Check cache first
            cached_streams = self.stream_cache.get_streams()
            if cached_streams is not None:
                return {"result": "success", "streams": cached_streams}

        # Fetch from API
        kwargs: dict[str, Any] = {"include_subscribed": include_subscribed}
        if include_public is not None:
            kwargs["include_public"] = include_public
        if include_all_active is not None:
            kwargs["include_all_active"] = include_all_active

        response = self.client.get_streams(**kwargs)
        if response["result"] == "success" and default_filters:
            self.stream_cache.set_streams(response["streams"])
        return response

    def get_users(
        self, client_gravatar: bool = True, include_custom_profile_fields: bool = False
    ) -> dict[str, Any]:
        """Get list of users."""
        # Check cache first
        default_filters = client_gravatar and not include_custom_profile_fields
        cached_users = self.user_cache.get_users() if default_filters else None
        if cached_users is not None:
            return {"result": "success", "members": cached_users}

        # Fetch from API
        response = self.client.get_users(
            {
                "client_gravatar": client_gravatar,
                "include_custom_profile_fields": include_custom_profile_fields,
            }
        )
        if response["result"] == "success" and default_filters:
            self.user_cache.set_users(response["members"])
        return response

    def get_stream_topics(self, stream_id: int) -> dict[str, Any]:
        """Get recent topics for a stream."""
        return self.client.get_stream_topics(stream_id)

    def add_reaction(
        self, message_id: int, emoji_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Add reaction to a message."""
        return self.client.add_reaction(
            {"message_id": message_id, "emoji_name": emoji_name, **kwargs}
        )

    def remove_reaction(
        self, message_id: int, emoji_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Remove reaction from a message."""
        return self.client.remove_reaction(
            {"message_id": message_id, "emoji_name": emoji_name, **kwargs}
        )

    # Additional endpoints used by v0.4 tools
    def update_message(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.client.update_message(request)

    def get_subscriptions(self) -> dict[str, Any]:
        return self.client.get_subscriptions()

    def update_subscription_settings(
        self, subscriptions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if hasattr(self.client, "update_subscription_settings"):
            return self.client.update_subscription_settings(
                subscription_data=subscriptions
            )
        return self.client.call_endpoint(
            "users/me/subscriptions/properties",
            method="PATCH",
            request={"subscription_data": subscriptions},
        )

    def add_subscriptions(
        self,
        subscriptions: Iterable[dict[str, Any]] | dict[str, Any] | None = None,
        *,
        streams: Iterable[dict[str, Any]] | dict[str, Any] | None = None,
        principals: list[str] | None = None,
        announce: bool | None = None,
        authorization_errors_fatal: bool | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Subscribe to streams or create-and-subscribe.

        Supports both "subscriptions=[...]" (preferred by tools) and
        "streams=[...]" (used by older client SDKs).
        """
        subs_input = subscriptions or streams or []
        if isinstance(subs_input, dict):
            subs_list = [subs_input]
        else:
            subs_list = list(subs_input)
        payload: dict[str, Any] = {"subscriptions": subs_list}
        if principals is not None:
            payload["principals"] = principals
        if announce is not None:
            payload["announce"] = announce
        if authorization_errors_fatal is not None:
            payload["authorization_errors_fatal"] = authorization_errors_fatal
        payload.update({k: v for k, v in kwargs.items() if v is not None})

        if hasattr(self.client, "add_subscriptions"):
            return self.client.add_subscriptions(
                streams=subs_list,
                **{k: v for k, v in payload.items() if k != "subscriptions"},
            )
        return self.client.call_endpoint(
            "users/me/subscriptions", method="POST", request=payload
        )

    def remove_subscriptions(
        self,
        subscriptions: Iterable[str],
        principals: Sequence[str] | Sequence[int] | None = None,
    ) -> dict[str, Any]:
        if hasattr(self.client, "remove_subscriptions"):
            return self.client.remove_subscriptions(
                streams=list(subscriptions), principals=principals
            )
        request: dict[str, Any] = {"subscriptions": list(subscriptions)}
        if principals is not None:
            request["principals"] = principals
        return self.client.call_endpoint(
            "users/me/subscriptions",
            method="DELETE",
            request=request,
        )

    def update_stream(self, stream_id: int, **updates: Any) -> dict[str, Any]:
        stream_data = {"stream_id": stream_id, **updates}
        if hasattr(self.client, "update_stream"):
            return self.client.update_stream(stream_data)
        return self.client.call_endpoint(
            f"streams/{stream_id}", method="PATCH", request=stream_data
        )

    def delete_stream(self, stream_id: int) -> dict[str, Any]:
        if hasattr(self.client, "delete_stream"):
            return self.client.delete_stream(stream_id)
        return self.client.call_endpoint(
            f"streams/{stream_id}", method="DELETE", request={}
        )

    def get_stream_id(self, stream: int | str) -> dict[str, Any]:
        if isinstance(stream, int):
            try:
                return self.client.call_endpoint(f"streams/{stream}")
            except Exception:
                return {"result": "error", "msg": "Failed to fetch stream info"}
        return self.client.get_stream_id(stream)

    def get_subscribers(self, stream_id: int) -> dict[str, Any]:
        """Get subscribers for a stream by ID.

        Note: SDK's get_subscribers expects stream name, not ID.
        We use call_endpoint directly with stream_id for efficiency.
        """
        return self.client.call_endpoint(
            f"streams/{stream_id}/members", method="GET", request={}
        )

    def mark_topic_as_read(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        if hasattr(self.client, "mark_topic_as_read"):
            return self.client.mark_topic_as_read(
                stream_id=stream_id, topic_name=topic_name
            )
        return self.client.call_endpoint(
            "mark_topic_as_read",
            method="POST",
            request={"stream_id": stream_id, "topic_name": topic_name},
        )

    def mute_topic(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        if hasattr(self.client, "mute_topic"):
            return self.client.mute_topic({"stream_id": stream_id, "topic": topic_name})
        return self.client.call_endpoint(
            "users/me/muted_topics",
            method="PATCH",
            request={"op": "add", "stream_id": stream_id, "topic": topic_name},
        )

    def unmute_topic(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        if hasattr(self.client, "unmute_topic"):
            return self.client.unmute_topic(stream_id=stream_id, topic=topic_name)
        return self.client.call_endpoint(
            "users/me/muted_topics",
            method="PATCH",
            request={"op": "remove", "stream_id": stream_id, "topic": topic_name},
        )

    def delete_topic(self, stream_id: int, topic_name: str) -> dict[str, Any]:
        if hasattr(self.client, "delete_topic"):
            return self.client.delete_topic(stream_id=stream_id, topic_name=topic_name)
        # Fallback; Zulip may use POST for delete_topic
        try:
            return self.client.call_endpoint(
                f"streams/{stream_id}/delete_topic",
                method="POST",
                request={"topic_name": topic_name},
            )
        except Exception:
            return {"result": "error", "msg": "Failed to delete topic"}

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
        if content is not None:
            request["content"] = content
        if topic is not None:
            request["topic"] = topic
        if stream_id:
            request["stream_id"] = stream_id
        request["propagate_mode"] = propagate_mode
        request["send_notification_to_old_thread"] = send_notification_to_old_thread
        request["send_notification_to_new_thread"] = send_notification_to_new_thread

        return self.client.update_message(request)

    # -------------------------
    # Missing wrapper methods (v0.4 blockers)
    # -------------------------

    def get_user_by_email(
        self, email: str, include_custom_profile_fields: bool = False
    ) -> dict[str, Any]:
        """Fetch a single user by email."""
        if hasattr(self.client, "get_user_by_email"):
            try:
                return self.client.get_user_by_email(
                    email, include_custom_profile_fields=include_custom_profile_fields
                )
            except TypeError:
                return self.client.get_user_by_email(
                    {
                        "email": email,
                        "include_custom_profile_fields": include_custom_profile_fields,
                    }
                )
        return self.client.call_endpoint(
            f"users/{quote(email, safe='')}",
            method="GET",
            request={"include_custom_profile_fields": include_custom_profile_fields},
        )

    def get_user_by_id(
        self, user_id: int, include_custom_profile_fields: bool = False
    ) -> dict[str, Any]:
        """Fetch a single user by numeric ID."""
        if hasattr(self.client, "get_user_by_id"):
            return self.client.get_user_by_id(
                user_id, include_custom_profile_fields=include_custom_profile_fields
            )
        return self.client.call_endpoint(
            f"users/{user_id}",
            method="GET",
            request={"include_custom_profile_fields": include_custom_profile_fields},
        )

    def get_message(self, message_id: int) -> dict[str, Any]:
        """Fetch a single message by ID."""
        if hasattr(self.client, "get_message"):
            try:
                return self.client.get_message(message_id=message_id)
            except TypeError:
                return self.client.get_message({"message_id": message_id})
        return self.client.call_endpoint(
            f"messages/{message_id}", method="GET", request={}
        )

    def update_message_flags(
        self, messages: list[int], op: str, flag: str
    ) -> dict[str, Any]:
        """Add/remove a flag on a list of messages."""
        payload = {"messages": messages, "op": op, "flag": flag}
        if hasattr(self.client, "update_message_flags"):
            return self.client.update_message_flags(payload)
        return self.client.call_endpoint(
            "messages/flags", method="POST", request=payload
        )

    def register(self, **kwargs: Any) -> dict[str, Any]:
        """Register an event queue (events API)."""
        if hasattr(self.client, "register"):
            try:
                return self.client.register(**kwargs)
            except TypeError:
                return self.client.register(kwargs)
        return self.client.call_endpoint("register", method="POST", request=kwargs)

    def deregister(self, queue_id: str, timeout: float | None = None) -> dict[str, Any]:
        """Delete an event queue by ID."""
        if hasattr(self.client, "deregister"):
            return self.client.deregister(queue_id, timeout=timeout)
        return self.client.call_endpoint(
            "events", method="DELETE", request={"queue_id": queue_id}
        )

    def get_events(self, **kwargs: Any) -> dict[str, Any]:
        """Poll events from a queue (long-poll capable)."""
        timeout = kwargs.pop("timeout", 90)
        # The SDK's longpolling=True retries read timeouts forever, ignoring
        # retry_on_errors. Bound a poll and let the listener/caller decide retry.
        return self.client.call_endpoint(
            "events", method="GET", request=kwargs, timeout=timeout, longpolling=False
        )

    # Convenience methods referenced by users_v25
    def update_user(self, user_id: int, **updates: Any) -> dict[str, Any]:
        if hasattr(self.client, "update_user"):
            try:
                return self.client.update_user(user_id, **updates)
            except TypeError:
                return self.client.update_user({"user_id": user_id, **updates})
        return self.client.call_endpoint(
            f"users/{user_id}", method="PATCH", request=updates
        )

    def update_presence(
        self, status: str, ping_only: bool = False, new_user_input: bool = True
    ) -> dict[str, Any]:
        if hasattr(self.client, "update_presence"):
            return self.client.update_presence(
                {
                    "status": status,
                    "ping_only": ping_only,
                    "new_user_input": new_user_input,
                }
            )
        return self.client.call_endpoint(
            "users/me/presence",
            method="POST",
            request={
                "status": status,
                "ping_only": ping_only,
                "new_user_input": new_user_input,
            },
        )

    def upload_file(self, file_content: bytes, filename: str) -> dict[str, Any]:
        """Upload a file to Zulip.

        Args:
            file_content: The file content as bytes
            filename: The name of the file

        Returns:
            API response with upload details including 'uri' field
        """
        import io

        # The Zulip client expects a file-like object
        file_obj = io.BytesIO(file_content)
        file_obj.name = filename

        if hasattr(self.client, "upload_file"):
            return self.client.upload_file(file_obj)

        # Fallback to direct API call
        import requests

        url = f"{self.base_url}/api/v1/user_uploads"
        files = {"file": (filename, file_content)}

        # Use proper authentication format
        import base64

        auth_string = f"{self.client.email}:{self.client.api_key}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        headers = {"Authorization": f"Basic {auth_bytes}"}

        response = requests.post(url, files=files, headers=headers, timeout=30)
        if response.status_code == 200:
            return {"result": "success", **response.json()}
        else:
            return {"result": "error", "msg": f"Upload failed: {response.text}"}

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
                raise RuntimeError(
                    streams_response.get("msg", "Failed to fetch streams")
                )

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
                summary.setdefault("unavailable_streams", []).append(stream_name)
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
