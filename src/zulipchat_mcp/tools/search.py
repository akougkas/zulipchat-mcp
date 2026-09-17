"""Search tools for ZulipChat MCP v0.4.0.

Core search operations: search messages, advanced search, narrow construction.
Analytics moved to ai_analytics.py for LLM elicitation.
"""

import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Literal, TypedDict, cast

from fastmcp import FastMCP

from ..config import get_client
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
) -> list[NarrowFilter]:
    """Build comprehensive narrow filter for Zulip API."""
    narrow: list[NarrowFilter] = []

    # Basic filters
    if stream:
        narrow.append({"operator": "stream", "operand": stream})
    if topic:
        narrow.append({"operator": "topic", "operand": topic})
    if sender:
        narrow.append({"operator": "sender", "operand": sender})
    # Add search operator only for actual search terms
    # Skip if text is empty, "*", or whitespace-only (wildcard = return all)
    if text and text.strip() and text.strip() != "*":
        narrow.append({"operator": "search", "operand": text})

    # Content type filters
    if has_attachment is not None:
        if has_attachment:
            narrow.append({"operator": "has", "operand": "attachment"})
        else:
            narrow.append({"operator": "has", "operand": "attachment", "negated": True})

    if has_link is not None:
        if has_link:
            narrow.append({"operator": "has", "operand": "link"})
        else:
            narrow.append({"operator": "has", "operand": "link", "negated": True})

    if has_image is not None:
        if has_image:
            narrow.append({"operator": "has", "operand": "image"})
        else:
            narrow.append({"operator": "has", "operand": "image", "negated": True})

    # Message state filters
    if is_private is not None:
        if is_private:
            narrow.append({"operator": "is", "operand": "private"})
        else:
            narrow.append({"operator": "is", "operand": "private", "negated": True})

    if is_starred is not None:
        if is_starred:
            narrow.append({"operator": "is", "operand": "starred"})
        else:
            narrow.append({"operator": "is", "operand": "starred", "negated": True})

    if is_mentioned is not None:
        if is_mentioned:
            narrow.append({"operator": "is", "operand": "mentioned"})
        else:
            narrow.append({"operator": "is", "operand": "mentioned", "negated": True})

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
    limit: int = 50,
    sort_by: Literal["newest", "oldest", "relevance"] = "relevance",
) -> dict[str, Any]:
    """Advanced search with fuzzy user resolution and comprehensive filtering."""
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
        if after_time is not None:
            after = parse_time(after_time)
            cutoff = max(cutoff, after) if cutoff else after
        before = parse_time(before_time) if before_time is not None else None
        if cutoff and before and cutoff > before:
            return {
                "status": "error",
                "error": "after_time must not exceed before_time",
            }
        cutoff_ts = cutoff.timestamp() if cutoff else None
        before_ts = before.timestamp() if before else None

        # Fetch from the requested end of the interval. Anchoring at its start
        # for a newest-first query silently returns the oldest matching sample.
        oldest_first = sort_by == "oldest"
        anchor = "oldest" if oldest_first else "newest"
        anchor_date = None
        boundary = cutoff if oldest_first else before
        if boundary:
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
            include_anchor=True,
            client_gravatar=True,
            apply_markdown=True,
        )

        if result.get("result") == "success":
            messages = result.get("messages", [])

            # Post-fetch time filtering (anchor_date positions anchor, doesn't filter)
            if cutoff_ts is not None:
                messages = [m for m in messages if m["timestamp"] >= cutoff_ts]
            if before_ts is not None:
                messages = [m for m in messages if m["timestamp"] <= before_ts]

            messages = sorted(
                messages,
                key=lambda message: (message["timestamp"], message["id"]),
                reverse=not oldest_first,
            )[:limit]

            # Process messages for response
            processed_messages = []
            for msg in messages:
                processed_messages.append(
                    {
                        "id": msg["id"],
                        "sender": msg["sender_full_name"],
                        "email": msg["sender_email"],
                        "timestamp": msg["timestamp"],
                        "content": (
                            msg["content"][:1000] + "..."
                            if len(msg["content"]) > 1000
                            else msg["content"]
                        ),
                        "type": msg["type"],
                        "stream": msg.get("display_recipient"),
                        "topic": msg.get("subject"),
                        "reactions": msg.get("reactions", []),
                        "flags": msg.get("flags", []),
                    }
                )

            return {
                "status": "success",
                "messages": processed_messages,
                "found": len(processed_messages),
                "anchor": result.get("anchor"),
                "narrow_applied": narrow,
                "sort_by": sort_by,
            }
        else:
            return {"status": "error", "error": result.get("msg", "Search failed")}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def advanced_search(
    query: str,
    search_type: list[Literal["messages", "users", "streams", "topics"]] | None = None,
    # Filters
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    has_attachment: bool | None = None,
    has_link: bool | None = None,
    is_private: bool | None = None,
    is_starred: bool | None = None,
    # Time range
    last_hours: int | None = None,
    last_days: int | None = None,
    # Response control
    limit: int = 100,
    sort_by: Literal["newest", "oldest", "relevance"] = "relevance",
    # Basic aggregations only
    aggregations: list[str] | None = None,
) -> dict[str, Any]:
    """Multi-faceted search with basic aggregations."""
    client = get_client()

    search_type = search_type or ["messages"]
    results = {}

    try:
        # Search messages
        if "messages" in search_type:
            msg_result = await search_messages(
                query=query,
                stream=stream,
                topic=topic,
                sender=sender,
                has_attachment=has_attachment,
                has_link=has_link,
                is_private=is_private,
                is_starred=is_starred,
                last_hours=last_hours,
                last_days=last_days,
                limit=limit,
                sort_by=sort_by,
            )
            results["messages"] = msg_result

        # Search users
        if "users" in search_type:
            users_response = await asyncio.to_thread(client.get_users)
            if users_response.get("result") == "success":
                users = users_response.get("members", [])
                matching_users = [
                    user
                    for user in users
                    if query.lower() in user.get("full_name", "").lower()
                    or query.lower() in user.get("email", "").lower()
                ][:limit]
                results["users"] = {
                    "status": "success",
                    "users": matching_users,
                    "count": len(matching_users),
                }
            else:
                results["users"] = {
                    "status": "error",
                    "error": users_response.get("msg", "User search failed"),
                }

        # Search streams
        if "streams" in search_type:
            streams_response = await asyncio.to_thread(client.get_streams)
            if streams_response.get("result") == "success":
                streams = streams_response.get("streams", [])
                matching_streams = [
                    stream
                    for stream in streams
                    if query.lower() in stream.get("name", "").lower()
                    or query.lower() in stream.get("description", "").lower()
                ][:limit]
                results["streams"] = {
                    "status": "success",
                    "streams": matching_streams,
                    "count": len(matching_streams),
                }
            else:
                results["streams"] = {
                    "status": "error",
                    "error": streams_response.get("msg", "Stream search failed"),
                }

        if "topics" in search_type:
            if not stream:
                results["topics"] = {
                    "status": "error",
                    "error": "Provide stream when searching topics",
                }
            else:
                stream_result = await asyncio.to_thread(client.get_stream_id, stream)
                if stream_result.get("result") != "success":
                    results["topics"] = {
                        "status": "error",
                        "error": stream_result.get("msg", "Stream not found"),
                    }
                else:
                    topics_result = await asyncio.to_thread(
                        client.get_stream_topics, stream_result["stream_id"]
                    )
                    if topics_result.get("result") != "success":
                        results["topics"] = {
                            "status": "error",
                            "error": topics_result.get("msg", "Topic search failed"),
                        }
                    else:
                        topics = [
                            item
                            for item in topics_result.get("topics", [])
                            if query.lower() in item.get("name", "").lower()
                        ][:limit]
                        results["topics"] = {
                            "status": "success",
                            "topics": topics,
                            "count": len(topics),
                        }

        # Basic aggregations only
        if (
            aggregations
            and "messages" in results
            and results["messages"].get("status") == "success"
        ):
            messages = results["messages"].get("messages", [])
            agg_results = {}

            if "count_by_user" in aggregations:
                user_counts = Counter(msg["sender"] for msg in messages)
                agg_results["count_by_user"] = dict(user_counts.most_common(10))

            if "count_by_stream" in aggregations:
                stream_counts = Counter(
                    msg["stream"]
                    for msg in messages
                    if isinstance(msg.get("stream"), str) and msg["stream"]
                )
                agg_results["count_by_stream"] = dict(stream_counts.most_common(10))

            results["aggregations"] = agg_results

        failures = [
            kind
            for kind in search_type
            if results.get(kind, {}).get("status") != "success"
        ]
        return {
            "status": (
                "error"
                if len(failures) == len(search_type)
                else "partial" if failures else "success"
            ),
            "query": query,
            "search_types": search_type,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "query": query}


async def construct_narrow(
    # Basic narrow operators
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    # Content filters
    search_text: str | None = None,
    has_attachment: bool | None = None,
    has_link: bool | None = None,
    has_image: bool | None = None,
    # Message state filters
    is_private: bool | None = None,
    is_starred: bool | None = None,
    is_mentioned: bool | None = None,
    is_unread: bool | None = None,
    is_muted: bool | None = None,
    is_followed: bool | None = None,
    # Time-based filters
    after_time: datetime | str | None = None,
    before_time: datetime | str | None = None,
    # ID-based filters
    message_id: int | None = None,
    near_message_id: int | None = None,
    # Advanced filters
    dm_with: str | list[str] | None = None,
    group_dm_with: str | list[str] | None = None,
) -> dict[str, Any]:
    """Construct narrow filter following Zulip API patterns."""
    try:
        if after_time is not None or before_time is not None:
            return {
                "status": "error",
                "error": "Zulip narrow filters cannot encode timestamps. Use search_messages with after_time/before_time instead.",
            }
        narrow: list[NarrowFilter] = []

        # Basic operators
        if stream:
            narrow.append({"operator": "stream", "operand": stream})
        if topic:
            narrow.append({"operator": "topic", "operand": topic})
        if sender:
            narrow.append({"operator": "sender", "operand": sender})

        # Content search
        if search_text:
            narrow.append({"operator": "search", "operand": search_text})

        # Has filters
        if has_attachment is not None:
            if has_attachment:
                narrow.append({"operator": "has", "operand": "attachment"})
            else:
                narrow.append(
                    {"operator": "has", "operand": "attachment", "negated": True}
                )

        if has_link is not None:
            if has_link:
                narrow.append({"operator": "has", "operand": "link"})
            else:
                narrow.append({"operator": "has", "operand": "link", "negated": True})

        if has_image is not None:
            if has_image:
                narrow.append({"operator": "has", "operand": "image"})
            else:
                narrow.append({"operator": "has", "operand": "image", "negated": True})

        # Is filters
        if is_private is not None:
            if is_private:
                narrow.append({"operator": "is", "operand": "private"})
            else:
                narrow.append({"operator": "is", "operand": "private", "negated": True})

        if is_starred is not None:
            if is_starred:
                narrow.append({"operator": "is", "operand": "starred"})
            else:
                narrow.append({"operator": "is", "operand": "starred", "negated": True})

        if is_mentioned is not None:
            if is_mentioned:
                narrow.append({"operator": "is", "operand": "mentioned"})
            else:
                narrow.append(
                    {"operator": "is", "operand": "mentioned", "negated": True}
                )

        if is_unread is not None:
            if is_unread:
                narrow.append({"operator": "is", "operand": "unread"})
            else:
                narrow.append({"operator": "is", "operand": "unread", "negated": True})

        if is_muted is not None:
            if is_muted:
                narrow.append({"operator": "is", "operand": "muted"})
            else:
                narrow.append({"operator": "is", "operand": "muted", "negated": True})

        if is_followed is not None:
            if is_followed:
                narrow.append({"operator": "is", "operand": "followed"})
            else:
                narrow.append(
                    {"operator": "is", "operand": "followed", "negated": True}
                )

        # ID-based filters
        if message_id:
            narrow.append({"operator": "id", "operand": message_id})

        if near_message_id:
            narrow.append({"operator": "near", "operand": near_message_id})

        # DM filters
        if dm_with:
            if isinstance(dm_with, str):
                narrow.append({"operator": "dm", "operand": dm_with})
            else:
                narrow.append({"operator": "dm", "operand": dm_with})

        if group_dm_with:
            narrow.append({"operator": "group-pm-with", "operand": group_dm_with})

        return {
            "status": "success",
            "narrow": narrow,
            "filter_count": len(narrow),
            "operators_used": [n["operator"] for n in narrow],
        }

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
            return {
                "status": "error",
                "error": result.get("msg", "Failed to check messages against narrow"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_search_tools(mcp: FastMCP) -> None:
    """Register core search tools with the MCP server."""
    mcp.tool(
        name="search_messages",
        description="Advanced search with fuzzy user matching and comprehensive filtering",
    )(search_messages)
    mcp.tool(
        name="advanced_search",
        description="Multi-faceted search across messages, users, streams with basic aggregations",
    )(advanced_search)
    mcp.tool(
        name="construct_narrow",
        description="Construct narrow filter following Zulip API patterns",
    )(construct_narrow)
    mcp.tool(
        name="check_messages_match_narrow",
        description="Check whether messages match a narrow filter",
    )(check_messages_match_narrow)
