"""Shared control-plane operations for Zulip-managed agent sessions."""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from ..config import get_config_manager
from ..utils.database_manager import DatabaseManager
from ..utils.logging import get_logger
from .agent_protocol import (
    DEFAULT_TOPIC_PREFIX,
    format_session_message,
    make_agent_id,
    make_session_id,
    make_session_topic,
    parse_control_message,
    project_name_from_dir,
    strip_message_markup,
)
from .client import OUTBOUND_CLIENT_NAME, ZulipClientWrapper

_session_binding_lock = threading.RLock()
_message_delivery_lock = threading.RLock()
_outbound_ids: OrderedDict[tuple[str, int], None] = OrderedDict()


@contextmanager
def _serialize_message_delivery() -> Iterator[None]:
    """Serialize sends and echoes until their Zulip ID is recorded."""
    with _message_delivery_lock:
        yield


@contextmanager
def _serialize_session_bindings() -> Iterator[None]:
    """Keep the topic occupancy check and write atomic within this process."""
    with _session_binding_lock:
        yield


logger = get_logger(__name__)

_REQUEST_ID_RE = re.compile(r"\bID:\s*([A-Za-z0-9_-]{4,})\b")


class AgentCoordinator:
    """Coordinates stable agent profiles, sessions, requests, and event routing."""

    def __init__(
        self,
        *,
        db: DatabaseManager | None = None,
        bot_client: ZulipClientWrapper | None = None,
        user_client: ZulipClientWrapper | None = None,
    ) -> None:
        self.db = db or DatabaseManager()
        self._bot_client = bot_client
        self._user_client = user_client

    @property
    def user_client(self) -> ZulipClientWrapper:
        if self._user_client is None:
            self._user_client = ZulipClientWrapper(
                get_config_manager(), use_bot_identity=False
            )
        return self._user_client

    @property
    def bot_client(self) -> ZulipClientWrapper:
        if self._bot_client is None:
            config = get_config_manager()
            self._bot_client = ZulipClientWrapper(
                config, use_bot_identity=config.has_bot_credentials()
            )
        return self._bot_client

    def default_owner_email(self) -> str:
        """Resolve the owning human account for a bound agent."""
        client = self.user_client
        _ = client.client
        if client.current_email:
            return client.current_email
        config = get_config_manager().config
        if config.email:
            return config.email
        raise ValueError("Unable to resolve the owning Zulip account")

    def discover_agent_stream(self) -> str:
        """Resolve the primary control stream."""
        configured = os.getenv("ZULIPCHAT_AGENT_STREAM")
        if configured:
            return configured

        preferred_streams = ["Agents-Channel", "AI Bots", "sandbox", "general"]
        result = self.bot_client.get_streams(
            include_public=True,
            include_subscribed=True,
        )
        if result.get("result") != "success":
            return "general"

        available = {stream["name"]: stream for stream in result.get("streams", [])}
        for stream_name in preferred_streams:
            if stream_name in available:
                return stream_name

        for stream in result.get("streams", []):
            if not stream.get("invite_only", True):
                return str(stream["name"])

        return "general"

    @staticmethod
    def _json_blob(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value or {}, sort_keys=True)

    @staticmethod
    def extract_request_id(topic: str | None, content: str | None) -> str | None:
        """Extract request IDs from topic names or message content."""
        if topic and "/request/" in topic.lower():
            return topic.rsplit("/", 1)[-1]
        if content:
            match = _REQUEST_ID_RE.search(content)
            if match:
                return match.group(1)
        return None

    def register_agent(
        self,
        *,
        agent_name: str = "claude",
        agent_type: str = "claude-code",
        owner_email: str | None = None,
        stream_name: str | None = None,
        topic_prefix: str = DEFAULT_TOPIC_PREFIX,
        metadata: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Register or update a stable agent profile."""
        resolved_owner = owner_email or self.default_owner_email()
        resolved_stream = stream_name or self.discover_agent_stream()
        agent_id = make_agent_id(resolved_owner, agent_type, agent_name)

        result = self.db.upsert_agent_profile(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_type=agent_type,
            owner_email=resolved_owner,
            stream_name=resolved_stream,
            topic_prefix=topic_prefix,
            metadata=self._json_blob(metadata),
        )
        if result.get("status") != "success":
            return result

        profile = self.db.get_agent_profile(agent_id)
        if profile is None:
            return {"status": "error", "error": "Agent profile was not persisted"}

        return {"status": "success", "agent": profile}

    @_serialize_session_bindings()
    def ensure_session(
        self,
        *,
        agent_id: str,
        external_session_id: str | None = None,
        topic_name: str | None = None,
        project_name: str | None = None,
        project_dir: str | None = None,
        status: str = "active",
        metadata: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Create or update a stable Zulip session binding."""
        profile = self.db.get_agent_profile(agent_id)
        if profile is None:
            return {"status": "error", "error": "Agent not found"}

        existing = None
        if external_session_id:
            existing = self.db.get_agent_session_by_external(
                agent_id, external_session_id
            )
        elif topic_name:
            existing = self.db.get_agent_session_for_topic(
                profile["stream_name"], topic_name
            )
        elif project_dir:
            existing = self.db.get_latest_agent_session(agent_id, project_dir)

        if existing and existing["agent_id"] != agent_id:
            return {
                "status": "error",
                "error": "Topic is already bound to another agent",
            }

        resolved_project = (
            project_name
            or (existing or {}).get("project_name")
            or project_name_from_dir(project_dir)
        )
        resolved_topic = (
            topic_name
            or (existing or {}).get("topic_name")
            or make_session_topic(
                resolved_project,
                str(profile["agent_name"]),
                external_session_id=external_session_id,
                topic_prefix=str(profile["topic_prefix"]),
            )
        )

        occupied = self.db.get_agent_session_for_topic(
            str(profile["stream_name"]), resolved_topic
        )
        if occupied and (
            not existing or occupied["session_id"] != existing["session_id"]
        ):
            return {
                "status": "error",
                "error": "Topic is already bound to another session",
            }

        if existing:
            update_result = self.db.update_agent_session(
                existing["session_id"],
                external_session_id=external_session_id
                or existing.get("external_session_id"),
                topic_name=resolved_topic,
                project_name=resolved_project,
                project_dir=project_dir or existing.get("project_dir"),
                host=socket.gethostname(),
                status=status,
                metadata=self._json_blob(metadata or existing.get("metadata") or {}),
            )
            if update_result.get("status") != "success":
                return update_result
            session = self.db.get_agent_session(existing["session_id"])
            if session is None:
                return {"status": "error", "error": "Session update failed"}
            return {"status": "success", "session": session, "created": False}

        session_id = make_session_id(agent_id, external_session_id or resolved_topic)
        result = self.db.upsert_agent_session(
            session_id=session_id,
            agent_id=agent_id,
            external_session_id=external_session_id,
            stream_name=str(profile["stream_name"]),
            topic_name=resolved_topic,
            owner_email=str(profile["owner_email"]),
            project_name=resolved_project,
            project_dir=project_dir,
            host=socket.gethostname(),
            status=status,
            metadata=self._json_blob(metadata),
        )
        if result.get("status") != "success":
            return result

        session = self.db.get_agent_session(session_id)
        if session is None:
            return {"status": "error", "error": "Session was not persisted"}
        return {"status": "success", "session": session, "created": True}

    def resolve_session(
        self,
        *,
        session_id: str | None = None,
        agent_id: str | None = None,
        project_dir: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve a session from explicit or contextual identifiers."""
        if session_id:
            return self.db.get_agent_session(session_id)
        if agent_id:
            return self.db.get_latest_agent_session(agent_id, project_dir)
        return None

    @_serialize_message_delivery()
    def send_session_message(
        self,
        *,
        session_id: str,
        content: str,
        category: str = "message",
        request_id: str | None = None,
        metadata: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Send a message into the bound Zulip topic for a session."""
        session = self.db.get_agent_session(session_id)
        if session is None:
            return {"status": "error", "error": "Session not found"}

        message = format_session_message(category, content, request_id=request_id)
        result = self.bot_client.send_message(
            message_type="stream",
            to=str(session["stream_name"]),
            content=message,
            topic=str(session["topic_name"]),
        )
        if result.get("result") != "success":
            return {"status": "error", "error": result.get("msg", "Failed to send")}

        message_id = result.get("id")
        if isinstance(message_id, int):
            _outbound_ids[(str(self.db._db.db_path), message_id)] = None
            if len(_outbound_ids) > 4096:
                _outbound_ids.popitem(last=False)
        persisted = self.db.create_session_event(
            event_id=(
                f"outbound:{message_id}"
                if message_id is not None
                else str(uuid.uuid4())
            ),
            agent_id=str(session["agent_id"]),
            session_id=str(session["session_id"]),
            stream_name=str(session["stream_name"]),
            topic_name=str(session["topic_name"]),
            sender_email=self.bot_client.current_email,
            direction="outbound",
            event_type=category,
            content=content,
            normalized_content=strip_message_markup(content),
            request_id=request_id,
            metadata=self._json_blob(metadata),
        )

        outcome = {
            "status": "success",
            "session_id": session_id,
            "message_id": result.get("id"),
            "category": category,
        }
        if persisted.get("status") != "success":
            outcome.update(
                status="partial",
                delivered=True,
                error="Zulip accepted the message, but local event persistence failed",
                retry_safe=False,
            )
        return outcome

    def create_request(
        self,
        *,
        session_id: str,
        prompt: str,
        request_type: str = "question",
        options: list[str] | None = None,
        context: str = "",
        source_event: str = "mcp-tool",
        metadata: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Create a persistent request and announce it in Zulip."""
        session = self.db.get_agent_session(session_id)
        if session is None:
            return {"status": "error", "error": "Session not found"}

        request_id = uuid.uuid4().hex
        create_result = self.db.create_agent_request(
            request_id=request_id,
            agent_id=str(session["agent_id"]),
            session_id=session_id,
            request_type=request_type,
            prompt=prompt,
            options=json.dumps(options) if options else None,
            context=context,
            source_event=source_event,
            metadata=self._json_blob(metadata),
        )
        if create_result.get("status") != "success":
            return create_result

        content_parts = [prompt]
        if options:
            content_parts.append(
                "Options:\n" + "\n".join(f"- {item}" for item in options)
            )
        if context:
            content_parts.append(f"Context: {context}")
        message_category = (
            "approval_request" if request_type == "approval" else "question"
        )
        try:
            send_result = self.send_session_message(
                session_id=session_id,
                content="\n\n".join(content_parts),
                category=message_category,
                request_id=request_id,
                metadata=metadata,
            )
        except Exception:
            self.db.update_agent_request(request_id, status="cancelled")
            raise
        if send_result.get("status") not in {"success", "partial"}:
            self.db.update_agent_request(request_id, status="cancelled")
            return send_result

        return {
            "status": send_result["status"],
            "request_id": request_id,
            "session_id": session_id,
            "message_id": send_result.get("message_id"),
            **(
                {
                    "delivered": True,
                    "retry_safe": False,
                    "error": send_result.get("error"),
                }
                if send_result["status"] == "partial"
                else {}
            ),
        }

    def wait_for_request(
        self, request_id: str, timeout_seconds: int = 300
    ) -> dict[str, Any]:
        """Poll the database for a session request response."""
        start = time.monotonic()
        while True:
            request = self.db.get_agent_request(request_id)
            if request is None:
                return {"status": "error", "error": "Request not found"}
            if request.get("status") in {
                "answered",
                "cancelled",
                "declined",
                "timeout",
            }:
                responded_at = request.get("responded_at")
                if isinstance(responded_at, datetime):
                    responded_at = responded_at.isoformat()
                return {
                    "status": "success",
                    "request_status": request.get("status"),
                    "response": request.get("response"),
                    "responded_at": responded_at,
                }
            if time.monotonic() - start >= timeout_seconds:
                break
            time.sleep(1)

        # A caller's polling timeout does not expire a shared pending request or
        # overwrite an answer arriving concurrently. A later poll can resume.
        return {"status": "error", "error": "Response timeout"}

    async def wait_for_request_async(
        self, request_id: str, timeout_seconds: int = 300
    ) -> dict[str, Any]:
        """Poll the database asynchronously for a session request response."""
        start = time.monotonic()
        while True:
            request = await asyncio.to_thread(self.db.get_agent_request, request_id)
            if request is None:
                return {"status": "error", "error": "Request not found"}
            if request.get("status") in {
                "answered",
                "cancelled",
                "declined",
                "timeout",
            }:
                responded_at = request.get("responded_at")
                if isinstance(responded_at, datetime):
                    responded_at = responded_at.isoformat()
                return {
                    "status": "success",
                    "request_status": request.get("status"),
                    "response": request.get("response"),
                    "responded_at": responded_at,
                }
            if time.monotonic() - start >= timeout_seconds:
                break
            await asyncio.sleep(1)

        return {"status": "error", "error": "Response timeout"}

    @_serialize_message_delivery()
    def record_inbound_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Classify and persist inbound Zulip messages for bound sessions."""
        sender_email = str(message.get("sender_email") or "")
        # Zulip's message client attribution precedes persistence in a separate
        # hook process. It suppresses echoes; it never authorizes a sender.
        if (
            message.get("client") == OUTBOUND_CLIENT_NAME
            and sender_email.lower() == str(self.bot_client.current_email).lower()
        ):
            return {"status": "ignored", "reason": "outbound_echo"}
        message_id = message.get("id")
        if isinstance(message_id, int) and (
            (str(self.db._db.db_path), message_id) in _outbound_ids
            or self.db.is_outbound_message(message_id)
        ):
            return {"status": "ignored", "reason": "outbound_echo"}

        topic_name = str(message.get("subject") or message.get("topic") or "")
        raw_content = str(message.get("content") or "")
        content = (
            strip_message_markup(raw_content)
            if message.get("content_type") == "text/html"
            else raw_content.strip()
        )
        stream_name = ""
        if message.get("type") == "stream":
            display_recipient = message.get("display_recipient")
            if isinstance(display_recipient, str):
                stream_name = display_recipient

        request_id = self.extract_request_id(topic_name, content)

        session = None
        if stream_name and topic_name:
            session = self.db.get_agent_session_for_topic(stream_name, topic_name)

        if session is None:
            return {"status": "ignored", "reason": "no_session"}

        if message_id is not None and self.db.has_session_event(
            f"inbound:{session['session_id']}:{message_id}"
        ):
            return {"status": "ignored", "reason": "duplicate"}

        parsed = parse_control_message(content)
        request_id = parsed.request_id or request_id
        authorized = sender_email.lower() == str(session["owner_email"]).lower()

        if not authorized:
            event_result = self.db.create_session_event(
                event_id=(
                    f"inbound:{session['session_id']}:{message['id']}"
                    if message.get("id")
                    else str(uuid.uuid4())
                ),
                agent_id=str(session["agent_id"]),
                session_id=str(session["session_id"]),
                stream_name=stream_name,
                topic_name=topic_name,
                sender_email=sender_email,
                direction="inbound",
                event_type="unauthorized",
                content=content,
                normalized_content=parsed.normalized_content,
                metadata="{}",
            )
            if event_result.get("status") == "error":
                return event_result
            if stream_name and topic_name:
                self.send_session_message(
                    session_id=str(session["session_id"]),
                    content=(
                        "Not authorized: only "
                        f"`{session['owner_email']}` can control this agent session."
                    ),
                )
            return {"status": "ignored", "reason": "unauthorized"}

        if request_id:
            request = self.db.get_agent_request(request_id)
            if (
                request
                and request.get("status") == "pending"
                and request.get("session_id") == session["session_id"]
                and (
                    (
                        request.get("request_type") == "approval"
                        and parsed.decision is not None
                    )
                    or (
                        request.get("request_type") != "approval"
                        and parsed.event_type == "question_response"
                    )
                )
            ):
                update_result = self.db.update_agent_request(
                    request_id,
                    status="answered",
                    response=parsed.decision or parsed.arguments,
                    responded_at=datetime.now(timezone.utc),
                )
                if update_result.get("status") == "error":
                    return update_result
        elif parsed.event_type == "approval_response":
            return {"status": "ignored", "reason": "approval_request_id_required"}

        event_result = self.db.create_session_event(
            event_id=(
                f"inbound:{session['session_id']}:{message['id']}"
                if message.get("id")
                else str(uuid.uuid4())
            ),
            agent_id=str(session["agent_id"]),
            session_id=str(session["session_id"]),
            stream_name=stream_name,
            topic_name=topic_name,
            sender_email=sender_email,
            direction="inbound",
            event_type=parsed.event_type,
            content=content,
            normalized_content=parsed.normalized_content,
            command=parsed.command,
            decision=parsed.decision,
            request_id=request_id,
        )
        if event_result.get("status") == "error":
            return event_result
        return {
            "status": "success",
            "session_id": session["session_id"],
            "event_type": parsed.event_type,
        }
