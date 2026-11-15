"""Owner-only Zulip inbox for an agent host: wait for requests, reply in place.

Mentioning the bot anywhere it can read, or sending it a direct message, files a
request. Only senders admitted by --mention-allow (default: the configured
owner, matched by user ID) are delivered with content. Everyone else is counted
and dropped: the bot never answers them and their text never reaches the host.
Replies go back to the exact conversation that produced the request.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

from ..config import get_config_manager
from ..core.agent_control import AgentCoordinator
from ..core.api_errors import api_error
from ..services.bot_mentions import ALL_SCOPE, BotMentionInbox, get_mention_inbox

REQUEST_PREFIX = "zulip:"
MAX_WAIT_SECONDS = 840  # Below the 900 s host timeout Clio and others use.
_POLL_SLICE_SECONDS = 20.0
_coordinator: AgentCoordinator | None = None


def _get_coordinator() -> AgentCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator()
    return _coordinator


def _refuse(error: str, code: str) -> dict[str, Any]:
    return {"status": "error", "error": error, "error_code": code, "retryable": False}


def _open_inbox() -> tuple[BotMentionInbox, Any, str, int | None] | dict[str, Any]:
    """Return the shared inbox plus the sender policy, or a refusal."""
    config = get_config_manager()
    if not config.has_bot_credentials():
        return _refuse(
            "The inbox needs a Generic bot: start the server with "
            "--zulip-bot-config-file",
            "BOT_NOT_CONFIGURED",
        )
    try:
        policy = config.mention_allow_policy()
    except ValueError as error:
        return _refuse(f"Invalid mention allow policy: {error}", "POLICY_INVALID")
    coordinator = _get_coordinator()
    inbox = get_mention_inbox(
        coordinator.bot_client,
        config.resolved_account().fingerprint,
        ALL_SCOPE,
        None,
    )
    return (
        inbox,
        policy,
        coordinator.default_owner_email(),
        coordinator.default_owner_id(),
    )


def _strip_bot_mention(content: str, bot_id: int | None, name: str | None) -> str:
    """Drop @-mentions of the bot itself; they are addressing, not request text."""
    patterns = [rf"@_?\*\*{re.escape(name)}(\|{bot_id})?\*\*"] if name else []
    if bot_id is not None:
        patterns.append(rf"@_?\*\*[^*|]+\|{bot_id}\*\*")
    for pattern in patterns:
        content = re.sub(pattern, "", content)
    return content.strip()


def _where(message: dict[str, Any]) -> str:
    if message.get("type") == "private":
        return "dm"
    return f"#{message.get('display_recipient')} > {message.get('subject')}"


def _context(
    message: dict[str, Any], count: int, allowed: Any, bot_id: int | None
) -> list[dict[str, Any]]:
    """Earlier messages in the same conversation, read with the bot identity."""
    narrow: list[dict[str, Any]]
    if message.get("type") == "private":
        others = [
            person["id"]
            for person in message.get("display_recipient") or []
            if isinstance(person, dict) and person.get("id") != bot_id
        ]
        narrow = [{"operator": "dm", "operand": others}]
    else:
        narrow = [
            {"operator": "channel", "operand": message.get("stream_id")},
            {"operator": "topic", "operand": message.get("subject")},
        ]
    response = _get_coordinator().bot_client.get_messages_raw(
        anchor=str(message["id"]),
        num_before=count,
        num_after=0,
        narrow=narrow,
        include_anchor=False,
        apply_markdown=False,
        use_cache=False,
    )
    if response.get("result") != "success":
        return []
    rows = []
    for item in response.get("messages", []):
        row: dict[str, Any] = {
            "from": item.get("sender_full_name"),
            "text": str(item.get("content", ""))[:500],
        }
        # Text written by anyone the policy does not admit is data, not a request.
        if not allowed(item):
            row["untrusted"] = True
        rows.append(row)
    return rows


async def wait_for_mentions(
    wait_seconds: int = 60,
    limit: int = 5,
    context_messages: int = 0,
    acknowledge: bool = True,
) -> dict[str, Any]:
    """Wait for the owner to @-mention or DM the bot; return their requests.

    Covers @-mentions in every channel the bot is subscribed to, direct
    messages to the bot, and topics handed off with teleport_chat. The server
    keeps the cursor, so each request is delivered once; call again to keep
    listening. Answer each request with reply(request_id, content).
    acknowledge=True reacts with :eyes: so the owner sees the request was taken.
    context_messages>0 adds that many earlier messages from the conversation;
    lines marked untrusted came from people the policy does not admit.
    Messages from anyone else are counted in ignored_unauthorized, never shown.
    """
    if not 0 <= wait_seconds <= MAX_WAIT_SECONDS:
        return _refuse(f"wait_seconds must be 0..{MAX_WAIT_SECONDS}", "BAD_REQUEST")
    if not 1 <= limit <= 20 or not 0 <= context_messages <= 20:
        return _refuse("limit must be 1..20 and context_messages 0..20", "BAD_REQUEST")
    opened = await asyncio.to_thread(_open_inbox)
    if isinstance(opened, dict):
        return opened
    inbox, policy, owner_email, owner_id = opened

    def allowed(message: dict[str, Any]) -> bool:
        return bool(
            policy.allows(
                message.get("sender_id"),
                message.get("sender_email"),
                owner_email,
                owner_id,
            )
        )

    cursor = inbox.delivered_cursor()
    if cursor is None:
        # First use: start from now so old mentions are not replayed as work.
        start = 0
        while True:
            page = await asyncio.to_thread(inbox.poll, start, 50, 0)
            following = int(page.get("next_after_message_id") or start)
            if following <= start:
                break
            start = following
        inbox.claim(None, start)
        cursor = inbox.delivered_cursor() or start

    deadline = time.monotonic() + wait_seconds
    claimed: list[dict[str, Any]] = []
    ignored = 0
    listener: dict[str, Any] = {}
    bot_id: int | None = None
    while True:
        remaining = max(0.0, deadline - time.monotonic())
        page = await asyncio.to_thread(
            inbox.poll, cursor, 50, min(remaining, _POLL_SLICE_SECONDS)
        )
        listener = page.get("listener", {})
        bot_id = page.get("bot_user_id")
        batch: list[dict[str, Any]] = []
        skipped = 0
        advance = cursor
        for message in page.get("messages", []):
            if len(batch) >= limit:
                break
            advance = max(advance, message["id"])
            if allowed(message):
                batch.append(message)
            else:
                skipped += 1
        else:
            # A full page was consumed; skip past tombstoned rows too.
            advance = max(advance, int(page.get("next_after_message_id") or advance))
        if advance > cursor:
            if not inbox.claim(cursor, advance):
                # Another host for this account took these; continue after them.
                cursor = inbox.delivered_cursor() or cursor
                continue
            cursor = advance
            claimed, ignored = batch, ignored + skipped
        if claimed or listener.get("error") or remaining <= 0:
            break

    bot = _get_coordinator().bot_client
    requests: list[dict[str, Any]] = []
    for message in claimed:
        request: dict[str, Any] = {
            "request_id": f"{REQUEST_PREFIX}{message['id']}",
            "from": message.get("sender_full_name"),
            "where": _where(message),
            "sent": datetime.fromtimestamp(
                message.get("timestamp", 0), tz=timezone.utc
            ).isoformat(timespec="seconds"),
            "text": _strip_bot_mention(
                str(message.get("content", "")), bot_id, inbox.bot_full_name
            ),
        }
        if message.get("content_truncated"):
            request["text_truncated"] = True
        if context_messages:
            request["context"] = await asyncio.to_thread(
                _context, message, context_messages, allowed, bot_id
            )
        if acknowledge:
            # Best effort: a failed reaction must not lose the request.
            await asyncio.to_thread(bot.add_reaction, message["id"], "eyes")
        requests.append(request)

    result: dict[str, Any] = {"status": "success", "requests": requests}
    if ignored:
        result["ignored_unauthorized"] = ignored
    if listener.get("error"):
        result["status"] = "partial"
        result["listener_error"] = listener["error"]
        result["retry_after_seconds"] = listener.get("retry_after_seconds", 0)
    elif not requests:
        result["hint"] = "No owner requests yet; call again to keep waiting."
    return result


async def reply(request_id: str, content: str) -> dict[str, Any]:
    """Answer a request from wait_for_mentions in the conversation it came from.

    Posts as the bot into the same channel topic or direct-message group. The
    destination is fixed by the request; only delivered owner requests qualify.
    """
    if (
        not request_id.startswith(REQUEST_PREFIX)
        or not request_id[len(REQUEST_PREFIX) :].isdigit()
    ):
        return _refuse("request_id must come from wait_for_mentions", "BAD_REQUEST")
    if not content.strip():
        return _refuse("Reply content cannot be empty", "BAD_REQUEST")
    opened = await asyncio.to_thread(_open_inbox)
    if isinstance(opened, dict):
        return opened
    inbox, policy, owner_email, owner_id = opened
    message_id = int(request_id[len(REQUEST_PREFIX) :])
    bot = _get_coordinator().bot_client
    message = inbox.message(message_id)
    if message is None and message_id <= (inbox.delivered_cursor() or 0):
        # An edit tombstones the inbox copy; the conversation is still valid.
        fetched = await asyncio.to_thread(
            bot.get_messages_raw,
            anchor=str(message_id),
            num_before=0,
            num_after=0,
            include_anchor=True,
            apply_markdown=False,
            use_cache=False,
        )
        found = [m for m in fetched.get("messages", []) if m.get("id") == message_id]
        message = found[0] if found else None
    delivered = inbox.delivered_cursor() or 0
    if (
        message is None
        or message_id > delivered
        or not policy.allows(
            message.get("sender_id"), message.get("sender_email"), owner_email, owner_id
        )
    ):
        return _refuse(
            "Unknown request: reply only to requests delivered by wait_for_mentions",
            "REQUEST_NOT_FOUND",
        )
    if message.get("type") == "private":
        bot_id = inbox.bot_user_id
        recipients = [
            person["id"]
            for person in message.get("display_recipient") or []
            if isinstance(person, dict) and person.get("id") != bot_id
        ]
        response = await asyncio.to_thread(
            bot.send_message, "private", recipients, content
        )
    else:
        response = await asyncio.to_thread(
            bot.send_message,
            "stream",
            message["stream_id"],
            content,
            message.get("subject"),
        )
    if response.get("result") != "success":
        return api_error(response, "Reply failed")
    result: dict[str, Any] = {
        "status": "success",
        "message_id": response.get("id"),
        "where": _where(message),
    }
    if response.get("message_link"):
        result["message_link"] = response["message_link"]
    return result


def watch_conversation(stream_id: int, topic: str) -> dict[str, Any] | None:
    """Route every owner message in a channel topic to the inbox."""
    opened = _open_inbox()
    if isinstance(opened, dict):
        return opened
    opened[0].watch(stream_id, topic)
    return None


async def teleport_chat(
    message: str,
    to: str = "me",
    topic: str | None = None,
    wait_seconds: int = 0,
) -> dict[str, Any]:
    """Hand this conversation to Zulip so the owner can continue it there.

    to="me" opens a direct message from the bot to the owner; to="#channel"
    with a topic posts there and routes every owner message in that topic to
    the inbox, mention or not. Continue with wait_for_mentions and reply.
    wait_seconds>0 also waits for the owner's first answer. To message other
    people use send_message.
    """
    target = to.strip()
    if not message.strip():
        return _refuse("message cannot be empty", "BAD_REQUEST")
    opened = await asyncio.to_thread(_open_inbox)
    if isinstance(opened, dict):
        return opened
    owner_id = opened[3]
    bot = _get_coordinator().bot_client
    if target.casefold() in {"me", "owner"}:
        if owner_id is None:
            return _refuse(
                "No human owner is configured; pass a user zuliprc with "
                "--zulip-config-file",
                "OWNER_UNKNOWN",
            )
        response = await asyncio.to_thread(
            bot.send_message, "private", [owner_id], message
        )
        where = "dm"
    elif target.startswith("#"):
        channel = target[1:].strip()
        if not channel or not topic or not topic.strip():
            return _refuse(
                "A channel handoff needs '#channel' and a topic", "BAD_REQUEST"
            )
        found = await asyncio.to_thread(bot.client.get_stream_id, channel)
        if found.get("result") != "success":
            return api_error(found, "Unknown channel")
        # The bot only receives messages from channels it is subscribed to.
        await asyncio.to_thread(bot.client.add_subscriptions, [{"name": channel}])
        response = await asyncio.to_thread(
            bot.send_message, "stream", found["stream_id"], message, topic.strip()
        )
        if response.get("result") == "success":
            await asyncio.to_thread(
                watch_conversation, int(found["stream_id"]), topic.strip()
            )
        where = f"#{channel} > {topic.strip()}"
    else:
        return _refuse(
            "teleport_chat hands the session to the owner (to='me' or "
            "'#channel'); use send_message to message other people",
            "BAD_REQUEST",
        )
    if response.get("result") != "success":
        return api_error(response, "Handoff failed")
    result: dict[str, Any] = {
        "status": "success",
        "message_id": response.get("id"),
        "where": where,
        "next": "Call wait_for_mentions to receive the owner's replies.",
    }
    if response.get("message_link"):
        result["message_link"] = response["message_link"]
    if wait_seconds:
        waited = await wait_for_mentions(wait_seconds=wait_seconds)
        result["requests"] = waited.get("requests", [])
        result.pop("next")
    return result
