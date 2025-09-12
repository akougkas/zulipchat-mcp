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

    def __init__(self, client: ZulipClientWrapper, db: DatabaseManager, stream_name: str = "Agents-Channel"):
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

    # Rest of the class remains the same as in the previous implementation
    # ... (full file contents remain identical)