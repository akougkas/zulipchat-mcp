"""Core messaging tools for ZulipChat MCP v0.4.0.

Clean implementation focused ONLY on core send/edit operations.
Reactions moved to emoji_messaging.py, bulk ops moved to mark_messaging.py.
"""

import asyncio
import difflib
import hashlib
import json
import threading
import time
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import get_bot_client, get_client, get_config_manager
from ..core.api_errors import api_error
from ..core.client import ZulipClientWrapper
from ..core.security import local_access_allowed


def sanitize_content(content: str, max_length: int = 50000) -> str:
    """Sanitize and truncate content."""
    if len(content) > max_length:
        return content[:max_length] + "\n... [Content truncated]"
    return content


# Agents occasionally repeat an identical send right after it succeeded.
# Repeats inside this window return the original result instead of posting.
DUPLICATE_SEND_WINDOW_SECONDS = 120.0
_recent_sends: dict[str, tuple[float, dict[str, Any]]] = {}
_recent_sends_lock = threading.Lock()


def _send_key(
    client: ZulipClientWrapper,
    type: str,
    to: Any,
    content: str,
    topic: str | None,
) -> str:
    type = {"private": "direct", "stream": "channel"}.get(type, type)
    recipients = sorted(
        str(item).strip().lower() for item in (to if isinstance(to, list) else [to])
    )
    identity = [
        str(getattr(client, "base_url", "")),
        str(getattr(client, "current_email", "")),
        str(getattr(client, "identity", "")),
    ]
    payload = json.dumps([identity, type, recipients, topic or "", content])
    return hashlib.sha256(payload.encode()).hexdigest()


def _match_people(people: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Exact full name, then first name, then full-name prefix; first rule wins."""
    names = [(u, str(u.get("full_name", "")).casefold()) for u in people]
    for matches in (
        [u for u, name in names if name == query],
        [u for u, name in names if name.split()[:1] == [query]],
        [u for u, name in names if name.startswith(query)],
    ):
        if matches:
            return matches
    return []


def _resolve_recipients(
    client: ZulipClientWrapper, to: list[str | int]
) -> list[str | int] | dict[str, Any]:
    """Turn names into user IDs; emails and IDs pass through unchanged.

    A name must match exactly one active user by full name, first name, or a
    unique full-name prefix. Anything else returns candidates and sends nothing,
    so a near-miss never reaches the wrong person.
    """
    names = [
        item
        for item in to
        if isinstance(item, str) and "@" not in item and not item.strip().isdigit()
    ]
    if not names:
        return [int(i) if isinstance(i, str) and i.isdigit() else i for i in to]
    roster = client.get_users()
    if roster.get("result") != "success":
        return api_error(roster, "Failed to fetch users for name resolution")
    people = [u for u in roster.get("members", []) if u.get("is_active", True)]
    resolved: list[str | int] = []
    for item in to:
        if item not in names:
            resolved.append(
                int(item) if isinstance(item, str) and item.isdigit() else item
            )
            continue
        query = str(item).strip().casefold()
        matches = _match_people(people, query)
        if len(matches) != 1:
            close = difflib.get_close_matches(
                query, [str(u.get("full_name", "")).casefold() for u in people], n=3
            )
            candidates = matches[:5] or [
                u for u in people if str(u.get("full_name", "")).casefold() in close
            ]
            return {
                "status": "error",
                "error": f"'{item}' matches {len(matches) or 'no'} users; nothing was sent",
                "error_code": "AMBIGUOUS_RECIPIENT" if matches else "UNKNOWN_RECIPIENT",
                "candidates": [
                    {"name": u.get("full_name"), "user_id": u.get("user_id")}
                    for u in candidates
                ],
                "retryable": False,
            }
        resolved.append(int(matches[0]["user_id"]))
    return resolved


async def send_message(
    type: Literal["stream", "private", "channel", "direct"],
    to: str | int | list[str | int],
    content: str,
    topic: str | None = None,
    allow_duplicate: bool = False,
    as_bot: bool = False,
) -> dict[str, Any]:
    """Send a channel or direct message; direct recipients may be names.

    type="direct" (or "private") takes names, emails or user IDs in to; a name
    must match one person exactly or nothing is sent and candidates are
    returned. type="channel" (or "stream") takes a channel name or ID plus topic.
    as_bot=True sends this one message with the configured bot credentials,
    which is how an agent speaks as itself; replies to a bot DM reach the bot.

    An identical message (same sender, recipients, topic and content) sent
    successfully in the last two minutes is not posted again; the result has
    duplicate_suppressed=True and the original message_id. Pass
    allow_duplicate=True only when the user explicitly wants a repeat.
    """
    if as_bot:
        if not local_access_allowed():
            return {
                "status": "error",
                "error": "as_bot is only available over stdio; HTTP uses the configured user identity",
                "retryable": False,
            }
        if not get_config_manager().has_bot_credentials():
            return {
                "status": "error",
                "error": "Bot credentials not configured; nothing was sent",
                "suggestion": "Start the server with --zulip-bot-config-file",
                "retryable": False,
            }
        client = get_bot_client()
    else:
        client = get_client()
    key = _send_key(client, type, to, content, topic)
    now = time.monotonic()
    if not allow_duplicate:
        with _recent_sends_lock:
            for stale in [
                k
                for k, (sent, _) in _recent_sends.items()
                if now - sent > DUPLICATE_SEND_WINDOW_SECONDS
            ]:
                del _recent_sends[stale]
            previous = _recent_sends.get(key)
        if previous:
            sent_at, result = previous
            return {
                **result,
                "duplicate_suppressed": True,
                "note": (
                    f"Identical message already sent {now - sent_at:.0f}s ago as "
                    f"message {result.get('message_id')}; it was not sent again. "
                    "Do not repeat it."
                ),
            }
    if type in ("private", "direct"):
        items = to if isinstance(to, list) else [to]
        recipients = await asyncio.to_thread(_resolve_recipients, client, items)
        if isinstance(recipients, dict):
            return recipients
        result = await _send_message(client, "private", recipients, content, topic)
    else:
        channel = to.lstrip("#") if isinstance(to, str) else to
        result = await _send_message(client, "stream", channel, content, topic)
    if result.get("status") == "success":
        with _recent_sends_lock:
            _recent_sends[key] = (now, result)
    return result


async def _send_message(
    client: ZulipClientWrapper,
    type: Literal["stream", "private"],
    to: Any,
    content: str,
    topic: str | None = None,
) -> dict[str, Any]:
    """Send using the identity captured by the enclosing operation."""

    # Validate stream messages have topic
    if type == "stream" and not topic:
        return {"status": "error", "error": "Topic required for stream messages"}

    # Validate recipient is not empty
    if not to or (isinstance(to, list) and len(to) == 0):
        return {"status": "error", "error": "Recipient list cannot be empty"}

    # Content sanitization
    safe_content = sanitize_content(content)

    # Send immediate message
    result = await asyncio.to_thread(client.send_message, type, to, safe_content, topic)

    if result.get("result") == "success":
        sent: dict[str, Any] = {
            "status": "success",
            "message_id": result.get("id"),
            "sent_as": getattr(client, "identity", None),
        }
        if result.get("message_link"):
            sent["message_link"] = result["message_link"]
        return sent
    else:
        return api_error(result, "Failed to send message")


async def edit_message(
    message_id: int,
    content: str | None = None,
    topic: str | None = None,
    stream_id: int | None = None,
    propagate_mode: Literal["change_one", "change_later", "change_all"] = "change_one",
    send_notification_to_old_thread: bool = False,
    send_notification_to_new_thread: bool = True,
) -> dict[str, Any]:
    """Edit message content, topic, or move between streams."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {
            "status": "error",
            "error": {
                "code": "INVALID_MESSAGE_ID",
                "message": f"Invalid message ID: {message_id}",
                "suggestions": ["Use search_messages to find valid message IDs"],
            },
        }

    if content is not None and not content.strip():
        return {"status": "error", "error": "Message content cannot be empty"}
    if content is None and topic is None and stream_id is None:
        return {
            "status": "error",
            "error": "Must provide content, topic, or stream_id to edit",
        }

    if propagate_mode not in ["change_one", "change_later", "change_all"]:
        return {
            "status": "error",
            "error": {
                "code": "INVALID_PROPAGATE_MODE",
                "message": f"Invalid propagate_mode: '{propagate_mode}'",
                "suggestions": [
                    "Use 'change_one' to edit only this message",
                    "Use 'change_later' to edit this and newer messages",
                    "Use 'change_all' to edit all messages in topic",
                ],
            },
        }

    client = get_client()

    safe_content = sanitize_content(content) if content is not None else None

    result = await asyncio.to_thread(
        client.edit_message,
        message_id=message_id,
        content=safe_content,
        topic=topic,
        propagate_mode=propagate_mode,
        send_notification_to_old_thread=send_notification_to_old_thread,
        send_notification_to_new_thread=send_notification_to_new_thread,
        stream_id=stream_id,
    )

    if result.get("result") == "success":
        changes = []
        if content is not None:
            changes.append("content")
        if topic is not None:
            changes.append("topic")
        if stream_id:
            changes.append("stream")

        return {
            "status": "success",
            "message_id": message_id,
            "changes": changes,
            "propagate_mode": propagate_mode,
        }
    else:
        return api_error(result, "Failed to edit message")


async def get_message(
    message_id: int,
    fresh: bool = False,
    content_format: Literal["rendered_html", "markdown"] = "rendered_html",
) -> dict[str, Any]:
    """Get a single message by ID; content_format="markdown" returns source text."""
    if not isinstance(message_id, int) or message_id <= 0:
        return {"status": "error", "error": "Invalid message ID"}

    client = get_client()

    try:
        options: dict[str, Any] = {"fresh": True} if fresh else {}
        if content_format == "markdown":
            options["apply_markdown"] = False
        result = await asyncio.to_thread(client.get_message, message_id, **options)

        if result.get("result") == "success":
            response = {
                "status": "success",
                "message": result.get("message", {}),
                "content_format": content_format,
            }
            if "_cache" in result:
                response["cache"] = result["_cache"]
            return response
        else:
            return api_error(result, "Message not found")

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def cross_post_message(
    source_message_id: int,
    target_streams: list[str],
    target_topic: str | None = None,
    add_reference: bool = True,
    custom_prefix: str | None = None,
) -> dict[str, Any]:
    """Share/duplicate a message across multiple streams."""
    if not isinstance(source_message_id, int) or source_message_id <= 0:
        return {"status": "error", "error": "Invalid source message ID"}

    if not target_streams:
        return {"status": "error", "error": "Must specify target streams"}

    client = get_client()

    try:
        # Get source message
        msg_result = await asyncio.to_thread(
            client.get_message, source_message_id, apply_markdown=False
        )
        if msg_result.get("result") != "success":
            return api_error(msg_result, "Source message not found")

        source_msg = msg_result.get("message", {})
        source_content = source_msg.get("content", "")
        source_topic = source_msg.get("subject", "")
        source_stream = source_msg.get("display_recipient", "")

        # Prepare cross-post content
        if add_reference:
            prefix = (
                custom_prefix
                or f"**Cross-posted from #{source_stream} > {source_topic}:**\n\n"
            )
            cross_post_content = prefix + source_content
        else:
            cross_post_content = source_content

        safe_content = sanitize_content(cross_post_content)

        # Post to target streams
        results = []
        for stream in target_streams:
            post_topic = target_topic or source_topic

            try:
                send_result = await _send_message(
                    client, "stream", stream, safe_content, post_topic
                )
            except Exception as e:
                # Retain confirmed earlier sends; never retry ambiguous writes.
                send_result = {"status": "error", "error": str(e)}

            if send_result.get("status") == "success":
                results.append(
                    {
                        "stream": stream,
                        "topic": post_topic,
                        "message_id": send_result.get("message_id"),
                        "status": "success",
                    }
                )
            else:
                results.append(
                    {
                        "stream": stream,
                        "topic": post_topic,
                        "status": "error",
                        "error": send_result.get("error", "Failed to post"),
                    }
                )

        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "error"]

        return {
            "status": "success" if not failed else "partial" if successful else "error",
            "source_message_id": source_message_id,
            "target_streams": target_streams,
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_messaging_tools(mcp: FastMCP) -> None:
    """Register core messaging tools with the MCP server."""
    mcp.tool(
        name="send_message",
        description=(
            "Send one message to a stream topic or users. Sends once; an identical "
            "repeat within two minutes is suppressed. The result reports sent_as."
        ),
    )(send_message)
    mcp.tool(
        name="edit_message",
        description="Edit message content, topic, or move between streams with propagation control",
    )(edit_message)
    mcp.tool(name="get_message", description="Get a single message by ID")(get_message)
    mcp.tool(
        name="cross_post_message",
        description="Share/duplicate message across multiple streams with attribution",
    )(cross_post_message)
