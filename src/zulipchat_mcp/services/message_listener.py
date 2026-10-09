"""Message listener service for processing Zulip events.

This service is designed to be run in the background to process
incoming messages and update pending user input requests.
"""

from __future__ import annotations

import asyncio
import threading
import uuid as _uuid
from datetime import datetime, timedelta, timezone
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
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._registration_error: str | None = None
        self._coordinator = AgentCoordinator(db=db, bot_client=client)

    async def start(self) -> None:
        """Start listening to Zulip events."""
        self.running = not self._stop_event.is_set()
        logger.info("Message listener started")

        while self.running:
            try:
                events = await self._get_events()
                if events is None:
                    # Error response (429, etc.); backoff before retrying
                    self._consecutive_errors += 1
                    delay = min(
                        self._BACKOFF_BASE ** min(self._consecutive_errors, 7),
                        self._BACKOFF_MAX,
                    )
                    logger.warning(
                        f"Backing off {delay:.0f}s (attempt {self._consecutive_errors})"
                    )
                    await asyncio.to_thread(self._stop_event.wait, delay)
                    continue
                self._consecutive_errors = 0
                for event in events:
                    if event.get("type") == "message":
                        await self._process_message(event.get("message", {}))
                    # Acknowledge only after persistence succeeds. Fetching a
                    # batch must not discard unprocessed events after a crash.
                    if isinstance(event.get("id"), int):
                        previous_id = self._last_event_id
                        self._last_event_id = event["id"]
                        try:
                            self._save_queue_state()
                        except Exception:
                            self._last_event_id = previous_id
                            raise
            except Exception as e:
                logger.error(f"Listener error: {e}")
                if self._queue_id is None:
                    self._registration_error = str(e)
                    self._ready.set()
                self._consecutive_errors += 1
                delay = min(
                    self._BACKOFF_BASE ** min(self._consecutive_errors, 7),
                    self._BACKOFF_MAX,
                )
                await asyncio.to_thread(self._stop_event.wait, delay)

    async def stop(self) -> None:
        """Stop listener loop."""
        self.request_stop()

    def request_stop(self) -> None:
        """Request listener shutdown from any thread."""
        self.running = False
        self._stop_event.set()

    def wait_until_ready(self, timeout: float = 20) -> None:
        if not self._ready.wait(timeout):
            raise RuntimeError(
                "Zulip listener queue was not ready before the deadline; no interactive prompt was sent"
            )
        if self._registration_error:
            raise RuntimeError(
                f"Zulip listener registration failed: {self._registration_error}"
            )

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
            }
            # Keep the SDK's 90s long-poll timeout, but disable its infinite
            # internal read-timeout retry loop so shutdown can make progress.
            resp = self.client.client.call_endpoint(
                "events", method="GET", request=params, longpolling=False, timeout=90
            )
            if resp.get("result") != "success":
                code = resp.get("code") or resp.get("msg")
                logger.warning(f"get_events returned error: {code}")
                if code and "BAD_EVENT_QUEUE_ID" in str(code):
                    await self._reset_queue()
                # Return None to signal error and trigger backoff
                return None

            return resp.get("events", [])
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
            self._ready.set()
            return
        await self._register_queue()

    async def _reset_queue(self) -> None:
        self._queue_id = None
        self._last_event_id = None
        await self._register_queue()

    async def _register_queue(self) -> None:
        self._ready.clear()
        self._registration_error = None
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
                await self._backfill_sessions()
                self._save_queue_state()
                self._ready.set()
                logger.info("Registered Zulip event queue for MessageListener")
            else:
                raise RuntimeError(f"Failed to register event queue: {resp.get('msg')}")
        except Exception as e:
            if self._queue_id is not None:
                try:
                    self.client.client.call_endpoint(
                        "events", method="DELETE", request={"queue_id": self._queue_id}
                    )
                except Exception:
                    logger.warning("Could not remove a failed listener queue")
            self._queue_id = None
            self._registration_error = str(e)
            self._ready.set()
            raise

    async def _backfill_sessions(self) -> None:
        """Register first, catch up by message ID, then deduplicate queue overlap."""
        for session in self.db.list_agent_sessions(include_closed=False):
            cursor = self.db.get_listener_message_cursor(str(session["session_id"]))
            created = session.get("created_at")
            if isinstance(created, datetime):
                created = (
                    created.replace(tzinfo=timezone.utc)
                    if created.tzinfo is None
                    else created
                )
            narrow = [
                {"operator": "stream", "operand": session["stream_name"]},
                {"operator": "topic", "operand": session["topic_name"]},
            ]
            if isinstance(created, datetime) and cursor is None:
                narrow.append(
                    {
                        "operator": "after",
                        "operand": (created - timedelta(days=1)).date().isoformat(),
                    }
                )
            for _ in range(100):
                response = await asyncio.to_thread(
                    self.client.get_messages_raw,
                    narrow=narrow,
                    anchor=str(cursor) if cursor is not None else "oldest",
                    num_before=0,
                    num_after=1000,
                    include_anchor=cursor is None,
                    apply_markdown=False,
                )
                if response.get("result") != "success":
                    raise RuntimeError(
                        f"Listener catch-up failed: {response.get('code') or response.get('msg')}"
                    )
                messages = sorted(
                    response.get("messages", []), key=lambda message: message["id"]
                )
                previous = cursor
                for message in messages:
                    message_id = message.get("id")
                    if not isinstance(message_id, int) or (
                        cursor is not None and message_id <= cursor
                    ):
                        continue
                    if not isinstance(created, datetime) or message.get(
                        "timestamp", 0
                    ) >= int(created.timestamp()):
                        await self._process_message(message)
                    self.db.save_listener_message_cursor(
                        str(session["session_id"]), message_id
                    )
                    cursor = message_id
                if response.get("found_newest") or not messages:
                    break
                if cursor == previous:
                    raise RuntimeError(
                        "Listener catch-up did not advance its message cursor"
                    )
            else:
                raise RuntimeError(
                    "Listener catch-up reached its page limit; retry to continue from the persisted cursor"
                )

    def _save_queue_state(self) -> None:
        """Persist current queue_id and last_event_id to DB."""
        if self._queue_id is not None:
            result = self.db.save_listener_state(self._queue_id, self._last_event_id)
            if result.get("status") == "error":
                raise RuntimeError("Failed to persist listener cursor")

    async def _process_message(self, message: dict[str, Any]) -> None:
        """Process a message event: update pending input requests and store as agent event."""
        if not message:
            return

        sender_email = message.get("sender_email")
        topic = message.get("subject") or message.get("topic")
        content = message.get("content")

        # Session-aware routing, owner policy, and request persistence.
        # Legacy requests lack a verifiable session/owner binding and must not
        # be answered merely because a message contains their request ID.
        result = self._coordinator.record_inbound_message(message)
        if result.get("status") == "error":
            raise RuntimeError("Failed to persist session message")
        if result.get("reason") == "no_session":
            return

        session = self.db.get_agent_session_for_topic(
            str(message.get("display_recipient") or ""), str(topic or "")
        )
        if session and isinstance(message.get("id"), int):
            self.db.save_listener_message_cursor(
                str(session["session_id"]), message["id"]
            )
        if result.get("reason") in {"outbound_echo", "duplicate"}:
            return

        # Always store as agent_event for poll_agent_events()
        result = self.db.create_agent_event(
            event_id=(
                f"zulip:{message['id']}" if message.get("id") else str(_uuid.uuid4())
            ),
            zulip_message_id=message.get("id"),
            topic=str(topic) if topic else "",
            sender_email=sender_email or "",
            content=content or "",
        )
        if result.get("status") == "error":
            raise RuntimeError("Failed to persist agent event")
