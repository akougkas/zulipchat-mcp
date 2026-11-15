"""Search tools for ZulipChat MCP v0.4.0.

Core search operations: search messages, advanced search, narrow construction.
Analytics moved to ai_analytics.py for LLM elicitation.
"""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Literal, TypedDict, cast

from ..config import get_client
from ..core.api_errors import api_error
from ..core.client import ZulipClientWrapper

NarrowOperand = str | int | list[str]


class NarrowFilterBase(TypedDict):
    operator: str
    operand: NarrowOperand


class NarrowFilter(NarrowFilterBase, total=False):
    negated: bool


class AmbiguousUserError(Exception):
    """Raised when user identifier matches multiple users."""

    def __init__(self, identifier: str, matches: list[dict[str, Any]]):
        self.identifier = identifier
        self.matches = matches
        match_strings = [f"{m.get('full_name')} ({m.get('email')})" for m in matches]
        super().__init__(
            f"Multiple matches for '{identifier}': {', '.join(match_strings[:5])}"
        )


class UserNotFoundError(Exception):
    """Raised when user identifier cannot be resolved."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"No user matching '{identifier}'")


async def resolve_user_identifier(
    identifier: str, client: ZulipClientWrapper
) -> dict[str, Any]:
    """Resolve partial names, emails, or IDs to full user info."""
    try:
        # Try exact email match first
        if "@" in identifier:
            response = await asyncio.to_thread(client.get_users)
            if response.get("result") == "success":
                users = response.get("members", [])
                exact_match = next(
                    (user for user in users if user.get("email") == identifier), None
                )
                if exact_match:
                    return exact_match

        # Get all users for fuzzy matching
        response = await asyncio.to_thread(client.get_users)
        if response.get("result") != "success":
            raise Exception(
                f"Failed to fetch users: {response.get('msg', 'Unknown error')}"
            )

        users = response.get("members", [])

        # Try exact full name match first
        exact_matches = [
            user
            for user in users
            if user.get("full_name", "").lower() == identifier.lower()
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]
        elif len(exact_matches) > 1:
            raise AmbiguousUserError(identifier, exact_matches)

        # Fuzzy matching with similarity scoring
        partial_matches = []
        for user in users:
            full_name = user.get("full_name", "")
            if (
                identifier.lower() in full_name.lower()
                or SequenceMatcher(None, full_name.lower(), identifier.lower()).ratio()
                > 0.6
            ):
                score = SequenceMatcher(
                    None, full_name.lower(), identifier.lower()
                ).ratio()
                partial_matches.append((score, user))

        # Sort by similarity score
        partial_matches.sort(key=lambda x: x[0], reverse=True)

        if not partial_matches:
            raise UserNotFoundError(identifier)
        elif len(partial_matches) == 1:
            return partial_matches[0][1]
        else:
            # Return best match if significantly better than others
            best_score = partial_matches[0][0]
            close_matches = [
                user for score, user in partial_matches if score > best_score - 0.2
            ]
            if len(close_matches) == 1:
                return close_matches[0]
            else:
                raise AmbiguousUserError(identifier, close_matches[:5])

    except (AmbiguousUserError, UserNotFoundError):
        raise
    except Exception as e:
        raise Exception(f"Failed to resolve user '{identifier}': {str(e)}") from e


EXCERPT_CHARS = 1000


def compact_message(
    msg: dict[str, Any], *, fixed_stream: bool = False, fixed_topic: bool = False
) -> dict[str, Any]:
    """One message as few tokens as possible: no nulls, no repeated context."""
    content = str(msg.get("content", ""))
    row: dict[str, Any] = {
        "id": msg["id"],
        "from": msg.get("sender_full_name"),
        "time": datetime.fromtimestamp(msg["timestamp"], tz=timezone.utc).isoformat(
            timespec="minutes"
        ),
    }
    if msg.get("type") == "private":
        row["dm"] = True
    else:
        if not fixed_stream:
            row["channel"] = msg.get("display_recipient")
        if not fixed_topic:
            row["topic"] = msg.get("subject")
    row["text"] = content[:EXCERPT_CHARS]
    if len(content) > EXCERPT_CHARS:
        row["truncated"] = True
    reactions: dict[str, int] = {}
    for reaction in msg.get("reactions") or []:
        name = reaction.get("emoji_name")
        reactions[name] = reactions.get(name, 0) + 1
    if reactions:
        row["reactions"] = reactions
    flags = msg.get("flags")
    if flags is not None and "read" not in flags:
        row["unread"] = True
    if flags and "starred" in flags:
        row["starred"] = True
    return row


def build_narrow(
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    text: str | None = None,
    has_attachment: bool | None = None,
    has_link: bool | None = None,
    has_image: bool | None = None,
    is_private: bool | None = None,
    is_starred: bool | None = None,
    is_mentioned: bool | None = None,
    last_hours: int | str | None = None,
    last_days: int | str | None = None,
    after_time: datetime | str | None = None,
    before_time: datetime | str | None = None,
    is_unread: bool | None = None,
) -> list[NarrowFilter]:
    """Build comprehensive narrow filter for Zulip API."""
    narrow: list[NarrowFilter] = []

    # Basic filters
    if stream:
        narrow.append({"operator": "channel", "operand": stream})
    if topic:
        narrow.append({"operator": "topic", "operand": topic})
    if sender:
        narrow.append({"operator": "sender", "operand": sender})
    # Add search operator only for actual search terms
    # Skip if text is empty, "*", or whitespace-only (wildcard = return all)
    if text and text.strip() and text.strip() != "*":
        narrow.append({"operator": "search", "operand": text})

    # Boolean filters: True requires the property, False excludes it.
    for operator, operand, value in (
        ("has", "attachment", has_attachment),
        ("has", "link", has_link),
        ("has", "image", has_image),
        ("is", "dm", is_private),
        ("is", "starred", is_starred),
        ("is", "mentioned", is_mentioned),
        ("is", "unread", is_unread),
    ):
        if value is not None:
            entry: NarrowFilter = {"operator": operator, "operand": operand}
            if not value:
                entry["negated"] = True
            narrow.append(entry)

    # Note: Time filters are NOT added to narrow - Zulip's get_messages API
    # doesn't support search operator with after:/before: syntax.
    # Time filtering is done client-side in search_messages().

    return narrow


async def search_messages(
    # Basic search parameters
    query: str | None = None,
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    # Advanced content filters
    has_attachment: bool | None = None,
    has_link: bool | None = None,
    has_image: bool | None = None,
    is_private: bool | None = None,
    is_starred: bool | None = None,
    is_mentioned: bool | None = None,
    # Time filters
    last_hours: int | str | None = None,
    last_days: int | str | None = None,
    after_time: datetime | str | None = None,
    before_time: datetime | str | None = None,
    # Response control
    limit: int = 20,
    sort_by: Literal["newest", "oldest", "relevance"] = "relevance",
    fresh: bool = False,
    content_format: Literal["markdown", "rendered_html"] = "markdown",
    cursor: str | None = None,
    is_unread: bool | None = None,
) -> dict[str, Any]:
    """Search or read messages; stream+topic with no query reads a thread.

    Filters combine: channel, topic, sender (name or email), text, time window,
    unread/mentioned/starred/DM flags. Rows are compact Markdown; channel and
    topic are omitted when the filter already fixes them. When
    sample.next_cursor is set, repeat the same call with cursor=<next_cursor>
    for the next page; no next_cursor means the query is exhausted.
    """
    client = get_client()

    try:
        # Resolve sender identifier to email if needed
        resolved_sender = sender
        if sender and "@" not in sender:
            try:
                user_info = await resolve_user_identifier(sender, client)
                resolved_sender = user_info.get("email")
            except AmbiguousUserError as e:
                return {
                    "status": "error",
                    "error": {
                        "code": "AMBIGUOUS_USER",
                        "message": str(e),
                        "suggestions": [
                            f"Did you mean: {m.get('full_name')} ({m.get('email')})?"
                            for m in e.matches[:3]
                        ],
                        "recovery": {
                            "tool": "get_users",
                            "hint": "List users to see all available options",
                        },
                    },
                }
            except UserNotFoundError as e:
                return {
                    "status": "error",
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": str(e),
                        "suggestions": [
                            "Use full email address",
                            "Check spelling",
                            "Use get_users to see available users",
                        ],
                        "recovery": {
                            "tool": "get_users",
                            "hint": "Search users to find correct identifier",
                        },
                    },
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": {
                        "code": "USER_RESOLUTION_FAILED",
                        "message": f"Could not resolve user '{sender}': {str(e)}",
                        "suggestions": [
                            "Use full email address",
                            "Try a different identifier",
                        ],
                    },
                }

        # Build narrow filter (without time - handled via anchor_date)
        narrow = build_narrow(
            stream=stream,
            topic=topic,
            sender=resolved_sender,
            text=query,
            has_attachment=has_attachment,
            has_link=has_link,
            has_image=has_image,
            is_private=is_private,
            is_starred=is_starred,
            is_mentioned=is_mentioned,
            is_unread=is_unread,
        )

        if not 1 <= limit <= 1000:
            return {"status": "error", "error": "limit must be between 1 and 1000"}

        def parse_time(value: datetime | str) -> datetime:
            parsed = (
                value
                if isinstance(value, datetime)
                else datetime.fromisoformat(value.replace("Z", "+00:00"))
            )
            return (
                parsed.replace(tzinfo=timezone.utc)
                if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc)
            )

        cutoff: datetime | None = None
        if last_hours is not None:
            hours = int(last_hours)
            if hours <= 0:
                return {"status": "error", "error": "last_hours must be positive"}
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        elif last_days is not None:
            days = int(last_days)
            if days <= 0:
                return {"status": "error", "error": "last_days must be positive"}
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            after = parse_time(after_time) if after_time is not None else None
            before = parse_time(before_time) if before_time is not None else None
        except ValueError as e:
            return {
                "status": "error",
                "error": "after_time/before_time must be ISO 8601, e.g. "
                f"2026-11-08 or 2026-11-08T00:00:00Z ({e})",
            }
        if after is not None:
            cutoff = max(cutoff, after) if cutoff else after
        if cutoff and before and cutoff > before:
            return {
                "status": "error",
                "error": "after_time must not exceed before_time",
            }
        cutoff_ts = cutoff.timestamp() if cutoff else None
        before_ts = before.timestamp() if before else None

        # A cursor is valid only for the same account, filters and order.
        query_key = hashlib.sha256(
            json.dumps(
                [
                    str(client.current_email),
                    str(client.identity),
                    str(client.read_snapshots.realm),
                    narrow,
                    str(last_hours),
                    str(last_days),
                    str(after_time),
                    str(before_time),
                    sort_by,
                ],
                default=str,
            ).encode()
        ).hexdigest()[:16]
        cursor_id: int | None = None
        if cursor is not None:
            cursor_message, _, cursor_key = cursor.partition(":")
            if cursor_key != query_key or not cursor_message.isdigit():
                return {
                    "status": "error",
                    "error": "cursor does not belong to this search; repeat the "
                    "call that returned it with the same filters, or omit cursor",
                }
            cursor_id = int(cursor_message)

        # Fetch from the requested end of the interval. Anchoring at its start
        # for a newest-first query silently returns the oldest matching sample.
        oldest_first = sort_by == "oldest"
        anchor = "oldest" if oldest_first else "newest"
        anchor_date = None
        boundary = cutoff if oldest_first else before
        if cursor_id is not None:
            anchor = str(cursor_id)
        elif boundary:
            anchor = "date"
            anchor_date = boundary.isoformat()
        num_before = 0 if oldest_first else limit
        num_after = limit if oldest_first else 0

        # Execute search
        result = await asyncio.to_thread(
            client.get_messages_raw,
            anchor=anchor,
            anchor_date=anchor_date,
            narrow=cast(list[dict[str, Any]], narrow),
            num_before=num_before,
            num_after=num_after,
            include_anchor=cursor_id is None,
            client_gravatar=True,
            apply_markdown=content_format == "rendered_html",
            use_cache=not fresh,
        )

        if result.get("result") == "success":
            messages = result.get("messages", [])

            # Post-fetch time filtering (anchor_date positions anchor, doesn't filter)
            in_window = [
                m
                for m in messages
                if (cutoff_ts is None or m["timestamp"] >= cutoff_ts)
                and (before_ts is None or m["timestamp"] <= before_ts)
            ]
            if oldest_first:
                reached_end = bool(result.get("found_newest")) or any(
                    before_ts is not None and m["timestamp"] > before_ts
                    for m in messages
                )
            else:
                reached_end = bool(result.get("found_oldest")) or any(
                    cutoff_ts is not None and m["timestamp"] < cutoff_ts
                    for m in messages
                )
            more = len(in_window) > limit or not reached_end
            messages = sorted(
                in_window,
                key=lambda message: (message["timestamp"], message["id"]),
                reverse=not oldest_first,
            )[:limit]
            next_cursor = (
                f"{messages[-1]['id']}:{query_key}" if more and messages else None
            )

            processed_messages = [
                compact_message(
                    msg, fixed_stream=bool(stream), fixed_topic=bool(stream and topic)
                )
                for msg in messages
            ]
            # Metadata precedes messages so a host that truncates long results
            # still shows the paging state.
            sample: dict[str, Any] = {
                "completeness": (
                    "partial" if next_cursor else "exhausted_visible_query"
                ),
                "ordering": "oldest_first" if oldest_first else "newest_first",
            }
            if next_cursor:
                sample["next_cursor"] = next_cursor
            truncated = sum(1 for row in processed_messages if row.get("truncated"))
            if truncated:
                sample["truncated_excerpts"] = truncated
            if cutoff:
                sample["after_time_utc"] = cutoff.isoformat()
            if before:
                sample["before_time_utc"] = before.isoformat()
            if stream:
                sample["channel"] = stream
            if stream and topic:
                sample["topic"] = topic
            return {
                "status": "success",
                "count": len(processed_messages),
                "sample": sample,
                "messages": processed_messages,
            }
        else:
            return api_error(result, "Search failed")

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_messages_match_narrow(
    msg_ids: list[int],
    narrow: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check whether a set of messages match a narrow filter."""
    client = get_client()

    try:
        request_data = {
            "msg_ids": msg_ids,
            "narrow": narrow,
        }

        result = await asyncio.to_thread(
            lambda: client.client.call_endpoint(
                "messages/matches_narrow", method="GET", request=request_data
            )
        )

        if result.get("result") == "success":
            messages = result.get("messages", {})
            matching_ids = list(messages.keys())

            return {
                "status": "success",
                "total_checked": len(msg_ids),
                "matching_count": len(matching_ids),
                "matching_message_ids": [int(msg_id) for msg_id in matching_ids],
                "non_matching_count": len(msg_ids) - len(matching_ids),
                "messages": messages,
                "narrow_applied": narrow,
            }
        else:
            return api_error(result, "Failed to check messages against narrow")

    except Exception as e:
        return {"status": "error", "error": str(e)}
