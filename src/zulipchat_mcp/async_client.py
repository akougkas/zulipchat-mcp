"""Async Zulip client implementation for better performance."""

import json
from datetime import datetime, timedelta
from typing import Any

import httpx

from .client import ZulipMessage, ZulipStream, ZulipUser
from .config import ZulipConfig


class AsyncZulipClient:
    """Async Zulip client for better performance."""

    def __init__(self, config: ZulipConfig) -> None:
        """Initialize async Zulip client.

        Args:
            config: Zulip configuration
        """
        self.config = config
        self.base_url = f"{config.site}/api/v1"
        self.auth = (config.email, config.api_key)
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncZulipClient":
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20
            ),
            auth=self.auth
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
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20
                ),
                auth=self.auth
            )
        return self.client

    async def send_message_async(
        self,
        message_type: str,
        to: str | list[str],
        content: str,
        topic: str | None = None
    ) -> dict[str, Any]:
        """Send message asynchronously.

        Args:
            message_type: Type of message (stream or private)
            to: Recipient(s)
            content: Message content
            topic: Topic for stream messages

        Returns:
            API response
        """
        client = self._ensure_client()

        data = {
            "type": message_type,
            "content": content
        }

        if message_type == "stream":
            data["to"] = to if isinstance(to, str) else to[0]
            if topic:
                data["topic"] = topic
        else:
            data["to"] = json.dumps(to if isinstance(to, list) else [to])

        response = await client.post(
            f"{self.base_url}/messages",
            data=data
        )
        response.raise_for_status()
        return response.json()

    async def get_messages_async(
        self,
        stream_name: str | None = None,
        topic: str | None = None,
        limit: int = 50,
        hours_back: int = 24
    ) -> list[ZulipMessage]:
        """Get messages asynchronously.

        Args:
            stream_name: Stream to filter by
            topic: Topic to filter by
            limit: Maximum number of messages
            hours_back: How far back to search

        Returns:
            List of messages
        """
        client = self._ensure_client()

        params = {
            "anchor": "newest",
            "num_before": limit,
            "num_after": 0
        }

        # Build narrow array
        narrow = []
        if stream_name:
            narrow.append({"operator": "stream", "operand": stream_name})
        if topic:
            narrow.append({"operator": "topic", "operand": topic})

        # Add time filter
        if hours_back:
            cutoff = datetime.now() - timedelta(hours=hours_back)
            narrow.append({
                "operator": "date",
                "operand": cutoff.strftime("%Y-%m-%d")
            })

        if narrow:
            params["narrow"] = json.dumps(narrow)

        response = await client.get(
            f"{self.base_url}/messages",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        if data["result"] == "success":
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
                    reactions=msg.get("reactions", [])
                )
                for msg in data["messages"]
            ]
        return []

    async def get_streams_async(self) -> list[ZulipStream]:
        """Get list of streams asynchronously.

        Returns:
            List of streams
        """
        client = self._ensure_client()

        response = await client.get(f"{self.base_url}/streams")
        response.raise_for_status()
        data = response.json()

        if data["result"] == "success":
            return [
                ZulipStream(
                    stream_id=stream["stream_id"],
                    name=stream["name"],
                    description=stream["description"],
                    is_private=stream.get("invite_only", False)
                )
                for stream in data["streams"]
            ]
        return []

    async def get_users_async(self) -> list[ZulipUser]:
        """Get list of users asynchronously.

        Returns:
            List of users
        """
        client = self._ensure_client()

        response = await client.get(f"{self.base_url}/users")
        response.raise_for_status()
        data = response.json()

        if data["result"] == "success":
            return [
                ZulipUser(
                    user_id=user["user_id"],
                    full_name=user["full_name"],
                    email=user["email"],
                    is_active=user["is_active"],
                    is_bot=user["is_bot"],
                    avatar_url=user.get("avatar_url")
                )
                for user in data["members"]
            ]
        return []

    async def add_reaction_async(
        self,
        message_id: int,
        emoji_name: str
    ) -> dict[str, Any]:
        """Add reaction to a message asynchronously.

        Args:
            message_id: ID of the message
            emoji_name: Name of the emoji

        Returns:
            API response
        """
        client = self._ensure_client()

        response = await client.post(
            f"{self.base_url}/messages/{message_id}/reactions",
            data={"emoji_name": emoji_name}
        )
        response.raise_for_status()
        return response.json()

    async def edit_message_async(
        self,
        message_id: int,
        content: str | None = None,
        topic: str | None = None
    ) -> dict[str, Any]:
        """Edit a message asynchronously.

        Args:
            message_id: ID of the message
            content: New content
            topic: New topic

        Returns:
            API response
        """
        client = self._ensure_client()

        data = {}
        if content:
            data["content"] = content
        if topic:
            data["topic"] = topic

        response = await client.patch(
            f"{self.base_url}/messages/{message_id}",
            data=data
        )
        response.raise_for_status()
        return response.json()

    async def search_messages_async(
        self,
        query: str,
        limit: int = 50
    ) -> list[ZulipMessage]:
        """Search messages asynchronously.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching messages
        """
        # Use the get_messages_async with search narrow
        narrow = [{"operator": "search", "operand": query}]

        client = self._ensure_client()
        params = {
            "anchor": "newest",
            "num_before": limit,
            "num_after": 0,
            "narrow": json.dumps(narrow)
        }

        response = await client.get(
            f"{self.base_url}/messages",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        if data["result"] == "success":
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
                    reactions=msg.get("reactions", [])
                )
                for msg in data["messages"]
            ]
        return []

    async def close(self) -> None:
        """Close the async client."""
        if self.client:
            await self.client.aclose()
            self.client = None


# Async wrapper functions for easy usage
async def send_message_async(
    config: ZulipConfig,
    message_type: str,
    to: str | list[str],
    content: str,
    topic: str | None = None
) -> dict[str, Any]:
    """Send message using async client.

    Args:
        config: Zulip configuration
        message_type: Type of message
        to: Recipient(s)
        content: Message content
        topic: Topic for stream messages

    Returns:
        API response
    """
    async with AsyncZulipClient(config) as client:
        return await client.send_message_async(message_type, to, content, topic)


async def get_messages_async(
    config: ZulipConfig,
    stream_name: str | None = None,
    topic: str | None = None,
    limit: int = 50
) -> list[ZulipMessage]:
    """Get messages using async client.

    Args:
        config: Zulip configuration
        stream_name: Stream to filter by
        topic: Topic to filter by
        limit: Maximum number of messages

    Returns:
        List of messages
    """
    async with AsyncZulipClient(config) as client:
        return await client.get_messages_async(stream_name, topic, limit)
