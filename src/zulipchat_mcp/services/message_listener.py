"""Message listener service for processing Zulip events.

This service is designed to be run in the background to process
incoming messages and update pending user input requests.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from ..core.client import ZulipClientWrapper
from ..utils.database_manager import DatabaseManager
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MessageListener:
    """Listens to Zulip event stream and processes responses."""

    def __init__(
        self,
        client: ZulipClientWrapper,
        db: DatabaseManager,
        stream_name: str = "Agents-Channel",
    ):
        self.client = client
        self.db = db
        self.running = False
        self.stream_name = stream_name
        self._queue_id: str | None = None
        self._last_event_id: int | None = None

    async def start(self) -> None:
        """Start listening to Zulip events."""
        self.running = True
        logger.info("Message listener started")

        while self.running:
            try:
                events = await self._get_events()
                for event in events:
                    if event.get("type") == "message":
                        await self._process_message(event.get("message", {}))
            except Exception as e:
                logger.error(f"Listener error: {e}")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop listener loop."""
        self.running = False

    async def _get_events(self) -> list[dict[str, Any]]:
        """Fetch events from Zulip using a shared event queue.

        Registers a queue on first use (messages only) narrowed to the
        `Agents-Channel` stream so we can process replies across topics.
        """
        # Ensure queue registration
        await self._ensure_queue()

        try:
            # Long-poll events; keep the timeout short to keep loop responsive
            params = {
                "queue_id": self._queue_id,
                "last_event_id": self._last_event_id,
                "dont_block": False,
                "timeout": 30,
            }
            resp = self.client.client.call_endpoint(
                "events", method="GET", request=params
            )
            if resp.get("result") != "success":
                code = resp.get("code") or resp.get("msg")
                logger.warning(f"get_events returned error: {code}")
                # If queue is invalid/expired, re-register and try once
                if code and "BAD_EVENT_QUEUE_ID" in str(code):
                    await self._reset_queue()
                return []

            events = resp.get("events", [])
            # Track last_event_id to resume correctly
            for ev in events:
                if isinstance(ev.get("id"), int):
                    self._last_event_id = ev["id"]
            return events
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return []

    async def _ensure_queue(self) -> None:
        if self._queue_id is not None:
            return
        await self._register_queue()

    async def _reset_queue(self) -> None:
        self._queue_id = None
        self._last_event_id = None
        await self._register_queue()

    async def _register_queue(self) -> None:
        try:
            request = {
                "event_types": ["message"],
                "apply_markdown": True,
                "client_gravatar": True,
                "narrow": [
                    {"operator": "stream", "operand": self.stream_name},
                ],
            }
            resp = self.client.client.call_endpoint(
                "register", method="POST", request=request
            )
            if resp.get("result") == "success":
                self._queue_id = resp.get("queue_id")
                last_event_id = resp.get("last_event_id")
                # Zulip can return last_event_id as int or str
                try:
                    self._last_event_id = (
                        int(last_event_id) if last_event_id is not None else None
                    )
                except Exception:
                    self._last_event_id = None
                logger.info("Registered Zulip event queue for MessageListener")
            else:
                logger.error(f"Failed to register event queue: {resp.get('msg')}")
        except Exception as e:
            logger.error(f"Exception during queue registration: {e}")

    def _extract_request_id(self, topic: str | None, content: str | None) -> str | None:
        if topic and topic.startswith("Agents/Input/"):
            parts = topic.split("/")
            if parts:
                return parts[-1]
        if content:
            match = re.search(r"\bID:\s*([A-Za-z0-9_-]{4,})\b", content)
            if match:
                return match.group(1)
        return None

    async def _process_message(self, message: dict[str, Any]) -> None:
        """Process a message event for pending input requests."""
        if not message:
            return

        sender_email = message.get("sender_email")
        if sender_email and sender_email == self.client.current_email:
            return

        topic = message.get("subject") or message.get("topic")
        content = message.get("content")
        request_id = self._extract_request_id(
            str(topic) if topic is not None else None,
            str(content) if content is not None else None,
        )
        if not request_id:
            return

        request = self.db.get_input_request(request_id)
        if not request or request.get("status") != "pending":
            return

        self.db.update_input_request(
            request_id,
            status="answered",
            response=content or "",
            responded_at=datetime.now(timezone.utc),
        )
