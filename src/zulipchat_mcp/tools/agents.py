"""Agent session tools for Zulip-controlled autonomous workflows."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from ..config import get_config_manager
from ..core.agent_control import AgentCoordinator
from ..core.service_manager import ensure_listener
from ..utils.database_manager import DatabaseManager
from ..utils.logging import LogContext, get_logger

logger = get_logger(__name__)

_coordinator: AgentCoordinator | None = None


def _get_coordinator() -> AgentCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator()
    return _coordinator


def register_agent(
    agent_name: str = "claude",
    agent_type: str = "claude-code",
    owner_email: str | None = None,
    stream_name: str | None = None,
    topic_prefix: str = "Agents/Session",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register or update a stable agent profile."""
    try:
        result = _get_coordinator().register_agent(
            agent_name=agent_name,
            agent_type=agent_type,
            owner_email=owner_email,
            stream_name=stream_name,
            topic_prefix=topic_prefix,
            metadata=metadata,
        )
        if result.get("status") != "success":
            return result
        agent = result["agent"]
        return {
            "status": "success",
            "agent_id": agent["agent_id"],
            "agent_name": agent["agent_name"],
            "agent_type": agent["agent_type"],
            "owner_email": agent["owner_email"],
            "stream": agent["stream_name"],
            "topic_prefix": agent["topic_prefix"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def ensure_agent_session(
    agent_id: str,
    external_session_id: str | None = None,
    topic_name: str | None = None,
    project_dir: str | None = None,
    project_name: str | None = None,
    status: str = "active",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or refresh the Zulip topic binding for an agent session."""
    try:
        result = _get_coordinator().ensure_session(
            agent_id=agent_id,
            external_session_id=external_session_id,
            topic_name=topic_name,
            project_dir=project_dir,
            project_name=project_name,
            status=status,
            metadata=metadata,
        )
        if result.get("status") != "success":
            return result
        session = result["session"]
        return {
            "status": "success",
            "session_id": session["session_id"],
            "agent_id": session["agent_id"],
            "external_session_id": session.get("external_session_id"),
            "stream_name": session["stream_name"],
            "topic_name": session["topic_name"],
            "owner_email": session["owner_email"],
            "project_name": session.get("project_name"),
            "status_name": session.get("status"),
            "created": result.get("created", False),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def agent_message(
    session_id: str,
    content: str,
    category: str = "message",
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a session-scoped message into the bound Zulip topic."""
    with LogContext(logger, tool="agent_message", session_id=session_id):
        try:
            return _get_coordinator().send_session_message(
                session_id=session_id,
                content=content,
                category=category,
                request_id=request_id,
                metadata=metadata,
            )
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def wait_for_response(
    request_id: str, timeout_seconds: int = 300
) -> dict[str, Any]:
    """Wait for a persisted agent request response."""
    try:
        coordinator = _get_coordinator()
        request = await asyncio.to_thread(coordinator.db.get_agent_request, request_id)
        listener_error = None
        if not request or request.get("status") not in {
            "answered",
            "cancelled",
            "declined",
            "timeout",
        }:
            try:
                await asyncio.to_thread(ensure_listener)
            except Exception as error:
                listener_error = str(error)
        result = await coordinator.wait_for_request_async(
            request_id, timeout_seconds=timeout_seconds
        )
        if listener_error:
            result["listener_error"] = listener_error
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


def request_user_input(
    session_id: str,
    question: str,
    options: list[str] | None = None,
    context: str = "",
    request_type: str = "question",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a session-bound question or approval request to Zulip."""
    try:
        ensure_listener()
        return _get_coordinator().create_request(
            session_id=session_id,
            prompt=question,
            request_type=request_type,
            options=options,
            context=context,
            source_event="mcp-tool",
            metadata=metadata,
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_sessions(
    agent_id: str | None = None, include_closed: bool = True
) -> dict[str, Any]:
    """List known agent sessions."""
    try:
        sessions = DatabaseManager().list_agent_sessions(
            agent_id=agent_id, include_closed=include_closed
        )
        for session in sessions:
            for key in ("created_at", "updated_at", "ended_at"):
                if isinstance(session.get(key), datetime):
                    session[key] = session[key].isoformat()
        return {"status": "success", "sessions": sessions}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def close_agent_session(
    session_id: str, status: str = "completed", summary: str = ""
) -> dict[str, Any]:
    """Close a session binding and optionally announce the result."""
    try:
        db = DatabaseManager()
        session = db.get_agent_session(session_id)
        if session is None:
            return {"status": "error", "error": "Session not found"}
        persisted = db.update_agent_session(session_id, status=status)
        if persisted.get("status") != "success":
            return persisted
        if summary:
            announcement = _get_coordinator().send_session_message(
                session_id=session_id,
                content=summary,
                category=status if status in {"completed", "failed"} else "message",
            )
            if announcement.get("status") != "success":
                return {
                    **announcement,
                    "status": "partial",
                    "session_id": session_id,
                    "session_closed": True,
                }
        return {
            "status": "success",
            "session_id": session_id,
            "status_name": status,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def poll_agent_events(
    limit: int = 50,
    agent_id: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
    auto_ack: bool = True,
    ack_event_ids: list[str] | None = None,
    include_audit: bool = False,
    mentions_stream: str | None = None,
    after_message_id: int | None = None,
    wait_seconds: float = 0,
    direct_messages: bool = False,
) -> dict[str, Any]:
    """Poll owner control events; use auto_ack=False and ack_event_ids for replay.

    include_audit=True also exposes outbound and unauthorized audit records.
    mentions_stream instead reads bot mentions without a pre-existing session.
    direct_messages=True reads every direct or group-direct message the bot
    receives instead (no @-mention needed; the bot's own messages are excluded).
    The two modes are mutually exclusive and share after_message_id,
    wait_seconds<=25, limit<=50 and the host-owned next_after_message_id cursor.
    Each direct-message event lists recipients and reply_to (all participants
    except the bot) so the host can answer in the same conversation.
    Only senders allowed by --mention-allow (default: the configured owner) are
    returned in events. Others appear only in ignored_unauthorized, without
    content, and the cursor still advances past them.
    The host owns durable message-ID deduplication and agent wake-up policy.
    """
    try:
        if mentions_stream is not None or direct_messages:
            if mentions_stream is not None and direct_messages:
                return {
                    "status": "error",
                    "error": "mentions_stream and direct_messages are mutually exclusive",
                    "retryable": False,
                }
            if session_id or agent_id or event_type or ack_event_ids or include_audit:
                return {
                    "status": "error",
                    "error": "Mention polling cannot be combined with session filters or acknowledgements",
                    "retryable": False,
                }
            return _poll_bot_mentions(
                mentions_stream, after_message_id, limit, wait_seconds
            )
        if after_message_id is not None or wait_seconds:
            return {
                "status": "error",
                "error": "after_message_id and wait_seconds require mentions_stream or direct_messages",
                "retryable": False,
            }
        db = DatabaseManager()
        if not 1 <= limit <= 500 or (ack_event_ids and len(ack_event_ids) > 500):
            return {
                "status": "error",
                "error": "Event batches must contain at most 500 entries and limit must be positive",
            }
        if ack_event_ids:
            acknowledged = db.ack_session_events(
                ack_event_ids, session_id=session_id, agent_id=agent_id
            )
            if acknowledged.get("status") != "success":
                return acknowledged
        events = db.get_unacked_session_events(
            limit=limit,
            agent_id=agent_id,
            session_id=session_id,
            event_type=event_type,
            include_audit=include_audit,
        )
        ids = [str(event["id"]) for event in events]
        if ids and auto_ack:
            acknowledged = db.ack_session_events(
                ids, session_id=session_id, agent_id=agent_id
            )
            if acknowledged.get("status") != "success":
                return {
                    "status": "partial",
                    "error": "Events read but acknowledgement failed",
                    "events": events,
                    "count": len(events),
                }
        result = {"status": "success", "events": events, "count": len(events)}
        if events or ack_event_ids:
            return result
        if not session_id and not agent_id:
            result["hint"] = (
                "This feed only holds owner replies to bound agent sessions. "
                "For @bot mentions call poll_agent_events(mentions_stream=CHANNEL, "
                "after_message_id=LAST_SEEN, wait_seconds=20, auto_ack=False) and "
                "pass next_after_message_id to the next call. For direct messages "
                "to the bot use direct_messages=True the same way. Do not re-run "
                "an identical search to watch for new messages."
            )
        try:
            ensure_listener()
        except Exception as error:
            result["listener_error"] = str(error)
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _poll_bot_mentions(
    stream: str | None,
    after_message_id: int | None,
    limit: int,
    wait_seconds: float = 0,
) -> dict[str, Any]:
    """Read the configured bot's mention (or, with no stream, direct-message) inbox.

    Message contents are never executed. Senders outside the --mention-allow
    policy are returned without content in ignored_unauthorized only.
    """
    direct = stream is None
    if (
        (stream is not None and (not stream.strip() or len(stream) > 200))
        or not 1 <= limit <= 50
        or (after_message_id is not None and after_message_id < 0)
        or not 0 <= wait_seconds <= 25
    ):
        return {
            "status": "error",
            "error": "Inbox polling requires a nonblank mentions_stream (when used), limit 1..50, nonnegative cursor and wait_seconds 0..25",
            "retryable": False,
        }
    config = get_config_manager()
    if not config.has_bot_credentials():
        return {
            "status": "error",
            "error": "Mention polling requires a configured Generic Zulip bot",
            "error_code": "BOT_NOT_CONFIGURED",
            "retryable": False,
        }
    try:
        policy = config.mention_allow_policy()
    except ValueError as error:
        return {
            "status": "error",
            "error": f"Invalid mention allow policy: {error}",
            "retryable": False,
        }
    coordinator = _get_coordinator()
    from ..services.bot_mentions import get_mention_inbox

    inbox = get_mention_inbox(
        coordinator.bot_client,
        config.resolved_account().fingerprint,
        None if stream is None else stream.strip(),
        after_message_id,
    )
    result = inbox.poll(after_message_id, limit, wait_seconds)
    owner = coordinator.default_owner_email().casefold()
    bot_user_id = result.get("bot_user_id")
    kind = "direct_message" if direct else "mention"
    events = []
    ignored = []
    messages = result.pop("messages")
    for message in messages:
        message_id = message["id"]
        if after_message_id is not None and message_id <= after_message_id:
            continue
        recipients = [
            {"id": person.get("id"), "email": person.get("email")}
            for person in (message.get("display_recipient") or [] if direct else [])
            if isinstance(person, dict)
        ]
        where: dict[str, Any] = (
            {"recipients": recipients}
            if direct
            else {"stream_id": message.get("stream_id")}
        )
        if not policy.allows(
            message.get("sender_id"), message.get("sender_email"), owner
        ):
            # Metadata only: a host must not be able to act on unauthorized text.
            ignored.append(
                {
                    "event_type": kind,
                    "message_id": message_id,
                    "sender_id": message.get("sender_id"),
                    "sender_email": message.get("sender_email"),
                    **where,
                    "timestamp": message.get("timestamp"),
                }
            )
            continue
        content = str(message.get("content", ""))
        event: dict[str, Any] = {
            "id": f"{kind}:{message_id}",
            "event_type": kind,
            "message_id": message_id,
            "sender_id": message.get("sender_id"),
            "sender_email": message.get("sender_email"),
            "is_configured_owner": str(message.get("sender_email", "")).casefold()
            == owner,
            **where,
        }
        if direct:
            event["message_type"] = "private"
            event["reply_to"] = [p for p in recipients if p["id"] != bot_user_id]
        else:
            event["stream_name"] = message.get("display_recipient")
            event["topic"] = message.get("subject")
        events.append(
            {
                **event,
                "timestamp": message.get("timestamp"),
                "content": content[:6000],
                "content_truncated": message.get("content_truncated", False),
                "last_edit_timestamp": message.get("last_edit_timestamp"),
            }
        )
    return {
        **result,
        "events": events,
        "count": len(events),
        "ignored_unauthorized": ignored,
        "authorization": policy.mode,
    }
