"""Message listener service for processing Zulip events.

This service is designed to be run in the background to process
incoming messages and update pending user input requests.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List

from ..core.client import ZulipClientWrapper
from ..utils.database_manager import DatabaseManager
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MessageListener:
    """Listens to Zulip event stream and processes responses."""

    def __init__(self, client: ZulipClientWrapper, db: DatabaseManager, stream_name: str = "Agent-Channel"):
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

    async def _get_events(self) -> List[Dict[str, Any]]:
        """Fetch events from Zulip using a shared event queue.

        Registers a queue on first use (messages only) narrowed to the
        `Agent-Channel` stream so we can process replies across topics.
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
            resp = self.client.client.call_endpoint("events", method="GET", request=params)
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
            resp = self.client.client.call_endpoint("register", method="POST", request=request)
            if resp.get("result") == "success":
                self._queue_id = resp.get("queue_id")
                last_event_id = resp.get("last_event_id")
                # Zulip can return last_event_id as int or str
                try:
                    self._last_event_id = int(last_event_id) if last_event_id is not None else None
                except Exception:
                    self._last_event_id = None
                logger.info("Registered Zulip event queue for MessageListener")
            else:
                logger.error(f"Failed to register event queue: {resp.get('msg')}")
        except Exception as e:
            logger.error(f"Exception during queue registration: {e}")

    async def _process_message(self, message: dict) -> None:
        """Check if message is response to pending request."""
        if not message or not message.get("content"):
            return

        pending = self.db.get_pending_input_requests()
        if not pending:
            pending = []

        # Avoid processing own bot messages
        try:
            sender_email = message.get("sender_email")
            if sender_email and sender_email == getattr(self.client, "current_email", None):
                return
        except Exception:
            pass

        # First try matching input requests
        for request in pending:
            if self._matches_request(message, request):
                self.db.update_input_request(
                    request["request_id"],
                    status="answered",
                    response=message.get("content"),
                    responded_at=datetime.utcnow(),
                )
                logger.info(
                    f"Matched response for request {request['request_id']} by message {message.get('id')}"
                )
                return

        # Otherwise, record as a generic agent chat event for later polling
        try:
            content = message.get("content", "")
            topic = message.get("subject") or message.get("topic") or ""
            zulip_mid = message.get("id")
            event_id = f"evt_{zulip_mid or datetime.utcnow().timestamp()}"
            self.db.create_agent_event(
                event_id=event_id,
                zulip_message_id=zulip_mid,
                topic=topic,
                sender_email=message.get("sender_email", ""),
                content=content,
            )
        except Exception as e:
            logger.error(f"Failed to store chat event: {e}")

    def _matches_request(self, message: dict, request: dict) -> bool:
        """Check if message matches request pattern.

        Strategies:
        - If content contains the request_id (e.g., when quoting), match.
        - If topic contains the short request_id, match.
        - If the message is in the same thread topic created for the request.
        """
        try:
            content: str = message.get("content", "")
            topic: str | None = message.get("subject") or message.get("topic")
            request_id = str(request.get("request_id", ""))
            short_id = request_id[:8]

            # Match by explicit request ID in content
            if request_id and re.search(re.escape(short_id), content, re.IGNORECASE):
                return True

            # Match by topic containing the request identifier
            if topic and (short_id in topic or request_id in topic):
                return True

            return False
        except Exception as e:
            logger.error(f"Failed to match request: {e}")
            return False
