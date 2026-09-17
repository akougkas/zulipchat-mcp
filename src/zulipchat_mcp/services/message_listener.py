"""Message listener service for processing Zulip events.

This service is designed to be run in the background to process
incoming messages and update pending user input requests.
"""

from __future__ import annotations

import asyncio
import uuid as _uuid
from typing import Any

from ..core.agent_control import AgentCoordinator
from ..core.client import ZulipClientWrapper
from ..utils.database_manager import DatabaseManager
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MessageListener:
    """Listens to Zulip event stream and processes responses."""

    _BACKOFF_BASE = 2.0
    _BACKOFF_MAX = 120.0

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
        self._consecutive_errors: int = 0
        self._coordinator = AgentCoordinator(db=db, bot_client=client)

    async def start(self) -> None:
        """Start listening to Zulip events."""
        self.running = True
        logger.info("Message listener started")

        while self.running:
            try:
                events = await self._get_events()
                if events is None:
                    # Error response (429, etc.); backoff before retrying
                    self._consecutive_errors += 1
                    delay = min(
                        self._BACKOFF_BASE**self._consecutive_errors,
                        self._BACKOFF_MAX,
                    )
                    logger.warning(
                        f"Backing off {delay:.0f}s (attempt {self._consecutive_errors})"
                    )
                    await asyncio.sleep(delay)
                    continue
                self._consecutive_errors = 0
                for event in events:
                    if event.get("type") == "message":
                        await self._process_message(event.get("message", {}))
            except Exception as e:
                logger.error(f"Listener error: {e}")
                self._consecutive_errors += 1
                delay = min(
                    self._BACKOFF_BASE**self._consecutive_errors,
                    self._BACKOFF_MAX,
                )
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        """Stop listener loop."""
        self.request_stop()

    def request_stop(self) -> None:
        """Request listener shutdown from any thread."""
        self.running = False

    async def _get_events(self) -> list[dict[str, Any]] | None:
        """Fetch events from Zulip using a shared event queue.

        Returns a list of events on success, empty list when there are no new
        events, or None on error (triggering backoff in the caller).
        """
        await self._ensure_queue()

        try:
            params = {
                "queue_id": self._queue_id,
                "last_event_id": self._last_event_id,
                "dont_block": False,
                "timeout": 30,
            }
            # zulip-py uses a 15s HTTP read timeout by default. With
            # `longpolling=True` it switches to a 90s timeout, which is
            # what /events long-polling needs — without it, every poll
            # fails with `Read timed out` after 15s before the server
            # has a chance to return from its (timeout=30) long-poll.
            resp = self.client.client.call_endpoint(
                "events", method="GET", request=params, longpolling=True
            )
            if resp.get("result") != "success":
                code = resp.get("code") or resp.get("msg")
                logger.warning(f"get_events returned error: {code}")
                if code and "BAD_EVENT_QUEUE_ID" in str(code):
                    await self._reset_queue()
                # Return None to signal error and trigger backoff
                return None

            events = resp.get("events", [])
            for ev in events:
                if isinstance(ev.get("id"), int):
                    self._last_event_id = ev["id"]
            if events:
                self._save_queue_state()
            return events
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return None

    async def _ensure_queue(self) -> None:
        if self._queue_id is not None:
            return
        state = self.db.get_listener_state()
        if state and state.get("queue_id"):
            self._queue_id = state["queue_id"]
            self._last_event_id = state.get("last_event_id")
            logger.info("Restored event queue from persisted state")
            return
        await self._register_queue()

    async def _reset_queue(self) -> None:
        self._queue_id = None
        self._last_event_id = None
        await self._register_queue()

    async def _register_queue(self) -> None:
        try:
            # No narrow — receive all messages (DMs + subscribed streams)
            request = {
                "event_types": ["message"],
                "apply_markdown": False,
                "client_gravatar": True,
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
                self._save_queue_state()
                logger.info("Registered Zulip event queue for MessageListener")
            else:
                logger.error(f"Failed to register event queue: {resp.get('msg')}")
        except Exception as e:
            logger.error(f"Exception during queue registration: {e}")

    def _save_queue_state(self) -> None:
        """Persist current queue_id and last_event_id to DB."""
        if self._queue_id is not None:
            self.db.save_listener_state(self._queue_id, self._last_event_id)

    async def _process_message(self, message: dict[str, Any]) -> None:
        """Process a message event: update pending input requests and store as agent event."""
        if not message:
            return

        sender_email = message.get("sender_email")
        if sender_email and sender_email == self.client.current_email:
            return

        topic = message.get("subject") or message.get("topic")
        content = message.get("content")

        # Session-aware routing, owner policy, and request persistence.
        # Legacy requests lack a verifiable session/owner binding and must not
        # be answered merely because a message contains their request ID.
        self._coordinator.record_inbound_message(message)

        # Always store as agent_event for poll_agent_events()
        self.db.create_agent_event(
            event_id=str(_uuid.uuid4()),
            zulip_message_id=message.get("id"),
            topic=str(topic) if topic else "",
            sender_email=sender_email or "",
            content=content or "",
        )
