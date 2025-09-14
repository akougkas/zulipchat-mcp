"""Advanced Search & Analytics tools for ZulipChat MCP v2.5.1.

This module implements the 2 enhanced search tools according to PLAN-REFACTOR.md:
1. advanced_search() - Multi-faceted search across Zulip
2. analytics() - Analytics and insights from message data

Features:
- Multi-faceted search across messages, users, streams, topics
- Advanced search with aggregations and time-range filtering
- Analytics with activity, sentiment, topics, and participation metrics
- Performance optimization with caching and timeouts
- Powerful narrow filtering support
- Chart data export capabilities
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Literal, cast

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.error_handling import get_error_handler
from ..core.identity import IdentityManager, IdentityType
from ..core.validation import (
    NarrowFilter,
    ParameterValidator,
)
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error
from ..utils.narrow_helpers import NarrowHelper

logger = get_logger(__name__)

# Response type definitions
SearchResults = dict[str, Any]
AnalyticsResponse = dict[str, Any]

# Token management constants
MAX_TOKENS_PER_RESPONSE = 20000  # Leave room for system messages and other content
AVG_CHARS_PER_TOKEN = 4  # Conservative estimate for token counting


def estimate_tokens(text: str) -> int:
    """Estimate token count for text content."""
    return len(text) // AVG_CHARS_PER_TOKEN


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
    """Resolve partial names, emails, or IDs to full user info.

    This function provides fuzzy matching for user identification, solving
    the problem where the Zulip narrow 'sender' operator ONLY accepts email
    addresses but users often provide partial names.

    Args:
        identifier: User identifier - can be email, partial name, or full name
        client: ZulipClientWrapper for API access

    Returns:
        Dict with user info including 'email' field for narrow construction

    Raises:
        AmbiguousUserError: When identifier matches multiple users
        UserNotFoundError: When identifier cannot be resolved
        Exception: For API errors

    Examples:
        user = await resolve_user_identifier("Jaime", client)
        # Returns: {"email": "jcernudagarcia@hawk.iit.edu", "full_name": "Jaime Garcia", ...}

        user = await resolve_user_identifier("user@example.com", client)
        # Returns: {"email": "user@example.com", ...}
    """
    try:
        # Try exact email match first (most efficient)
        if "@" in identifier:
            # Get all users to check if email exists
            response = await client.get_users()
            if response.get("result") == "success":
                users = response.get("members", [])
                exact_match = next(
                    (user for user in users if user.get("email") == identifier), None
                )
                if exact_match:
                    return exact_match
            # Email not found, fall through to fuzzy matching
        else:
            # Get all users for fuzzy matching
            response = await client.get_users()
            if response.get("result") != "success":
                raise Exception(f"Failed to fetch users: {response.get('msg', 'Unknown error')}")

            users = response.get("members", [])

            # Try exact full name match first
            exact_matches = [
                user for user in users
                if user.get("full_name", "").lower() == identifier.lower()
            ]
            if len(exact_matches) == 1:
                return exact_matches[0]
            elif len(exact_matches) > 1:
                raise AmbiguousUserError(identifier, exact_matches)

            # Try partial name matching with similarity scoring
            def similarity_score(user_name: str, query: str) -> float:
                """Calculate similarity score between user name and query."""
                return SequenceMatcher(None, user_name.lower(), query.lower()).ratio()

            # Find partial matches with good similarity
            partial_matches = []
            for user in users:
                full_name = user.get("full_name", "")
                # Check if query is contained in name or if similarity is high
                if (
                    identifier.lower() in full_name.lower()
                    or similarity_score(full_name, identifier) > 0.6
                ):
                    score = similarity_score(full_name, identifier)
                    partial_matches.append((score, user))

            # Sort by similarity score (highest first)
            partial_matches.sort(key=lambda x: x[0], reverse=True)

            if not partial_matches:
                raise UserNotFoundError(identifier)
            elif len(partial_matches) == 1:
                return partial_matches[0][1]
            else:
                # Check if top match is significantly better than others
                best_score = partial_matches[0][0]
                close_matches = [
                    user for score, user in partial_matches
                    if score > best_score - 0.2  # Within 20% of best score
                ]

                if len(close_matches) == 1:
                    return close_matches[0]
                else:
                    raise AmbiguousUserError(identifier, close_matches[:5])

    except (AmbiguousUserError, UserNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error resolving user identifier '{identifier}': {e}")
        raise Exception(f"Failed to resolve user '{identifier}': {str(e)}")


def truncate_for_tokens(results: dict[str, Any], max_tokens: int = MAX_TOKENS_PER_RESPONSE) -> tuple[dict[str, Any], bool]:
    """Truncate search results to fit within token limits.

    Returns:
        Tuple of (truncated_results, was_truncated)
    """
    import json

    # Convert to JSON string to measure size
    full_json = json.dumps(results, ensure_ascii=False)
    estimated_tokens = estimate_tokens(full_json)

    if estimated_tokens <= max_tokens:
        return results, False

    # Need to truncate - prioritize by result type
    truncated = {"truncated": True, "original_token_estimate": estimated_tokens}
    remaining_tokens = max_tokens - estimate_tokens(json.dumps(truncated, ensure_ascii=False))

    # Prioritize message content first, then other results
    if "messages" in results and remaining_tokens > 1000:
        # Keep most recent messages
        messages = results["messages"][:min(50, len(results["messages"]))]  # Max 50 messages
        truncated["messages"] = messages
        remaining_tokens -= estimate_tokens(json.dumps({"messages": messages}, ensure_ascii=False))

    # Add other result types if space permits
    for key in ["streams", "users", "topics", "aggregations"]:
        if key in results and remaining_tokens > 500:
            # Truncate these lists to reasonable sizes
            if isinstance(results[key], list):
                truncated[key] = results[key][:20]  # Max 20 items
            else:
                truncated[key] = results[key]
            remaining_tokens -= estimate_tokens(json.dumps({key: truncated[key]}, ensure_ascii=False))

    # Add summary stats
    if "summary" in results:
        truncated["summary"] = results["summary"]

    return truncated, True


# Data structures for search and analytics
@dataclass
class TimeRange:
    """Time range specification for searches and analytics."""

    days: int | None = None
    hours: int | None = None
    start: datetime | None = None
    end: datetime | None = None

    def to_narrow_filters(self) -> list[NarrowFilter]:
        """Convert to narrow filters for Zulip API."""
        filters = []

        if self.start:
            filters.append(
                NarrowFilter(
                    operator="search", operand=f"after:{self.start.isoformat()}"
                )
            )
        elif self.days:
            # Ensure days is an integer (handle string input from MCP)
            days = int(self.days) if isinstance(self.days, str) else self.days
            start_time = datetime.now() - timedelta(days=days)
            filters.append(
                NarrowFilter(
                    operator="search", operand=f"after:{start_time.isoformat()}"
                )
            )
        elif self.hours:
            # Ensure hours is an integer (handle string input from MCP)
            hours = int(self.hours) if isinstance(self.hours, str) else self.hours
            start_time = datetime.now() - timedelta(hours=hours)
            filters.append(
                NarrowFilter(
                    operator="search", operand=f"after:{start_time.isoformat()}"
                )
            )

        if self.end:
            filters.append(
                NarrowFilter(
                    operator="search", operand=f"before:{self.end.isoformat()}"
                )
            )

        return filters


class AggregationType:
    """Types of aggregations available for search results."""

    COUNT_BY_USER = "count_by_user"
    COUNT_BY_STREAM = "count_by_stream"
    COUNT_BY_TIME = "count_by_time"
    WORD_FREQUENCY = "word_frequency"
    EMOJI_USAGE = "emoji_usage"


# Global instances
_config_manager: ConfigManager | None = None
_identity_manager: IdentityManager | None = None
_parameter_validator: ParameterValidator | None = None
_error_handler = get_error_handler()

# Cache for search results
_search_cache: dict[str, Any] = {}


def _get_managers() -> tuple[ConfigManager, IdentityManager, ParameterValidator]:
    """Get or create manager instances."""
    global _config_manager, _identity_manager, _parameter_validator

    if _config_manager is None:
        _config_manager = ConfigManager()

    if _identity_manager is None:
        _identity_manager = IdentityManager(_config_manager)

    if _parameter_validator is None:
        _parameter_validator = ParameterValidator()

    return _config_manager, _identity_manager, _parameter_validator


def _generate_cache_key(
    query: str,
    search_type: Sequence[str],
    narrow: list[NarrowFilter] | None,
    **kwargs: Any,
) -> str:
    """Generate cache key for search results."""
    key_parts = [
        query,
        "|".join(sorted(search_type)),
        str(
            hash(
                tuple(
                    (f.operator.value, str(f.operand), f.negated) for f in narrow or []
                )
            )
        ),
        str(hash(tuple(sorted(kwargs.items())))),
    ]
    return "|".join(key_parts)


def _extract_search_highlights(content: str, query: str) -> list[str]:
    """Extract highlighted search terms from content."""
    if not query or not content:
        return []

    # Simple highlighting - find query terms in content
    query_terms = query.lower().split()
    highlights = []

    for term in query_terms:
        if term in content.lower():
            # Find surrounding context
            pos = content.lower().find(term)
            start = max(0, pos - 30)
            end = min(len(content), pos + len(term) + 30)
            highlight = content[start:end].strip()
            if highlight not in highlights:
                highlights.append(highlight)

    return highlights[:5]  # Limit to 5 highlights


def _analyze_message_sentiment(content: str) -> dict[str, Any]:
    """Simple sentiment analysis of message content."""
    positive_words = [
        "good",
        "great",
        "excellent",
        "awesome",
        "love",
        "like",
        "happy",
        "thanks",
        "thank you",
    ]
    negative_words = [
        "bad",
        "terrible",
        "awful",
        "hate",
        "dislike",
        "sad",
        "angry",
        "frustrated",
        "problem",
        "issue",
    ]

    content_lower = content.lower()
    positive_count = sum(1 for word in positive_words if word in content_lower)
    negative_count = sum(1 for word in negative_words if word in content_lower)

    if positive_count > negative_count:
        sentiment = "positive"
        confidence = min(0.9, 0.5 + (positive_count - negative_count) * 0.1)
    elif negative_count > positive_count:
        sentiment = "negative"
        confidence = min(0.9, 0.5 + (negative_count - positive_count) * 0.1)
    else:
        sentiment = "neutral"
        confidence = 0.5

    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "positive_indicators": positive_count,
        "negative_indicators": negative_count,
    }


def _extract_topics_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract topic patterns from message content."""
    topics: defaultdict[str, int] = defaultdict(int)
    word_frequency: Counter[str] = Counter()

    for message in messages:
        content = message.get("content", "").lower()
        # Remove HTML tags and URLs
        content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"http[s]?://\S+", "", content)

        # Extract words (simple tokenization)
        words = re.findall(r"\b[a-zA-Z]{3,}\b", content)
        word_frequency.update(words)

        # Simple topic detection based on common patterns
        if any(word in content for word in ["meeting", "call", "conference"]):
            topics["meetings"] += 1
        if any(word in content for word in ["project", "task", "deadline"]):
            topics["project_management"] += 1
        if any(word in content for word in ["bug", "issue", "error", "fix"]):
            topics["technical_issues"] += 1
        if any(word in content for word in ["release", "deploy", "launch"]):
            topics["releases"] += 1
        if any(word in content for word in ["question", "help", "how"]):
            topics["questions"] += 1

    return {
        "topic_distribution": dict(topics),
        "top_words": word_frequency.most_common(20),
        "total_messages_analyzed": len(messages),
    }


async def advanced_search(
    query: str,
    search_type: list[Literal["messages", "users", "streams", "topics"]] | None = None,
    # Simple narrow building (NEW - enhanced with NarrowHelper)
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    has_attachment: bool | None = None,
    has_link: bool | None = None,
    is_private: bool | None = None,
    is_starred: bool | None = None,
    # Advanced narrow support (existing)
    narrow: list[NarrowFilter] | None = None,
    # Advanced search options
    highlight: bool = True,
    aggregations: list[str] | None = None,
    time_range: TimeRange | None = None,
    sort_by: Literal["newest", "oldest", "relevance"] = "relevance",
    limit: int = 100,
    # Performance options
    use_cache: bool = True,
    timeout: int = 30,
) -> SearchResults:
    """Multi-faceted search across Zulip with enhanced narrow building capabilities.

    This enhanced tool provides powerful search capabilities with both simple parameter-based
    filtering (using NarrowHelper utilities) and advanced narrow filtering.

    SIMPLE USAGE (NEW - enhanced with NarrowHelper):
        Use basic parameters for common searches with automatic narrow building

    ADVANCED USAGE (existing v2.5.0):
        Use narrow parameter for complex filtering and time_range for advanced time filtering

    Args:
        query: Search query string
        search_type: Types of content to search (defaults to ["messages"])

        # Simple narrow building parameters (NEW)
        stream: Stream name to limit search to
        topic: Topic name to limit search to
        sender: Sender email to filter by
        has_attachment: Filter for messages with/without attachments
        has_link: Filter for messages with/without links
        is_private: Filter for private/public messages
        is_starred: Filter for starred/unstarred messages

        # Advanced filtering (existing)
        narrow: Additional narrow filters for message search (overrides simple params)
        highlight: Whether to include search term highlights
        aggregations: List of aggregation types to compute
        time_range: Time range specification for search
        sort_by: Sort order for results
        limit: Maximum number of results to return
        use_cache: Whether to use cached results
        timeout: Search timeout in seconds

    Returns:
        SearchResults with comprehensive search results and aggregations

    Examples:
        # Simple searches with enhanced narrow building (NEW)
        await advanced_search("python deployment", stream="engineering")
        await advanced_search("bug report", topic="issues", has_attachment=True)
        await advanced_search("code review", sender="senior-dev@example.com", is_starred=True)

        # Multi-faceted search with simple filtering (NEW)
        await advanced_search("docker",
                              search_type=["messages", "topics"],
                              stream="devops",
                              aggregations=["count_by_user"])

        # Advanced search with explicit narrow filters (existing v2.5.0)
        narrow_filters = [NarrowFilter("stream", "development")]
        await advanced_search("code review",
                              narrow=narrow_filters,
                              time_range=TimeRange(days=7),
                              highlight=True)

        # Using NarrowHelper for complex scenarios (NEW)
        await advanced_search("deployment issues",
                              narrow=NarrowHelper.build_basic_narrow(
                                  stream="infrastructure",
                                  has_link=True,
                                  last_days=3
                              ))
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "search.advanced_search"}):
        with LogContext(
            logger, tool="advanced_search", query=query, search_types=search_type
        ):
            track_tool_call("search.advanced_search")

            try:
                config, identity_manager, validator = _get_managers()

                # Default search type
                if search_type is None:
                    search_type = ["messages"]

                # Validate search parameters
                if not query.strip():
                    return {"status": "error", "error": "Query cannot be empty"}

                if limit < 1 or limit > 1000:
                    return {
                        "status": "error",
                        "error": "Limit must be between 1 and 1000",
                    }

                # Resolve sender identifier to email if needed (NEW in v2.5.1)
                if sender:
                    try:
                        user_info = await resolve_user_identifier(sender, client)
                        original_sender = sender
                        sender = user_info.get("email")
                        logger.debug(f"Resolved sender '{original_sender}' to '{sender}'")
                    except AmbiguousUserError as e:
                        # Return structured error with suggestions for recovery
                        return {
                            "status": "error",
                            "error": {
                                "code": "AMBIGUOUS_USER",
                                "message": str(e),
                                "suggestions": [
                                    f"Did you mean: {match.get('full_name')} ({match.get('email')})?"
                                    for match in e.matches[:3]
                                ],
                                "recovery": {
                                    "tool": "advanced_search",
                                    "hint": "Use the full email address or more specific name"
                                }
                            }
                        }
                    except UserNotFoundError as e:
                        # Return structured error with recovery guidance
                        return {
                            "status": "error",
                            "error": {
                                "code": "USER_NOT_FOUND",
                                "message": str(e),
                                "suggestions": [
                                    "Check the spelling of the user's name",
                                    "Try using the full email address instead",
                                    "Use 'list_users' tool to see all available users"
                                ],
                                "recovery": {
                                    "tool": "manage_users",
                                    "params": {"operation": "list"}
                                }
                            }
                        }
                    except Exception as e:
                        return {
                            "status": "error",
                            "error": {
                                "code": "USER_RESOLUTION_FAILED",
                                "message": f"Failed to resolve sender '{sender}': {str(e)}",
                                "suggestions": [
                                    "Try using the email address directly",
                                    "Check your connection and try again"
                                ]
                            }
                        }

                # Build effective narrow filters with enhanced logic
                simple_params_provided = any(
                    [
                        stream,
                        topic,
                        sender,
                        has_attachment is not None,
                        has_link is not None,
                        is_private is not None,
                        is_starred is not None,
                    ]
                )

                if narrow:
                    # Advanced mode: use provided narrow filters
                    effective_narrow = narrow
                elif simple_params_provided:
                    # Simple mode: build from basic parameters using NarrowHelper
                    effective_narrow = NarrowHelper.build_basic_narrow(
                        stream=stream,
                        topic=topic,
                        sender=sender,
                        text=query,  # Include search query in narrow
                        has_attachment=has_attachment,
                        has_link=has_link,
                        is_private=is_private,
                        is_starred=is_starred,
                    )
                else:
                    # Default: just search for query
                    effective_narrow = [NarrowHelper.search_text(query)]

                # Check cache if enabled (updated to include simple params)
                cache_key = _generate_cache_key(
                    query,
                    search_type,
                    effective_narrow,
                    highlight=highlight,
                    aggregations=aggregations,
                    time_range=time_range,
                    sort_by=sort_by,
                    limit=limit,
                    # Include simple params in cache key
                    stream=stream,
                    topic=topic,
                    sender=sender,
                    has_attachment=has_attachment,
                    has_link=has_link,
                    is_private=is_private,
                    is_starred=is_starred,
                )

                if use_cache and cache_key in _search_cache:
                    cached_result = _search_cache[cache_key]
                    cached_result["from_cache"] = True
                    logger.info(f"Returning cached search results for query: {query}")
                    return cached_result

                # Execute search with appropriate identity and error handling
                async def _execute_search(
                    client: ZulipClientWrapper, params: dict[str, Any]
                ) -> dict[str, Any]:
                    results: dict[str, Any] = {
                        "status": "success",
                        "query": query,
                        "search_types": search_type,
                        "results": {},
                        "aggregations": {},
                        "metadata": {
                            "total_results": 0,
                            "search_time": datetime.now().isoformat(),
                            "sort_by": sort_by,
                            "limit": limit,
                            "from_cache": False,
                        },
                    }

                    # Search messages
                    if "messages" in search_type:
                        message_narrow = effective_narrow.copy()

                        # Add time range filters if specified
                        if time_range:
                            message_narrow.extend(time_range.to_narrow_filters())

                        # Convert to API format
                        narrow_dict = NarrowHelper.to_api_format(message_narrow)

                        # Determine anchor and num_before/after based on sort order
                        if sort_by == "newest":
                            anchor = "newest"
                            num_before = limit
                            num_after = 0
                        elif sort_by == "oldest":
                            anchor = "oldest"
                            num_before = 0
                            num_after = limit
                        else:  # relevance
                            anchor = "newest"
                            num_before = limit // 2
                            num_after = limit // 2

                        # Use ZulipClientWrapper get_messages_raw for better performance
                        message_result = client.get_messages_raw(
                            narrow=narrow_dict,
                            anchor=anchor,
                            num_before=num_before,
                            num_after=num_after,
                            include_anchor=True,
                            apply_markdown=True,
                            client_gravatar=True,
                        )

                        if message_result.get("result") == "success":
                            messages = message_result.get("messages", [])

                            # Add highlights if requested
                            if highlight:
                                for message in messages:
                                    content = message.get("content", "")
                                    message["highlights"] = _extract_search_highlights(
                                        content, query
                                    )

                            results["results"]["messages"] = {
                                "count": len(messages),
                                "messages": messages[:limit],
                                "has_more": len(messages) >= limit,
                            }
                            results["metadata"]["total_results"] += len(messages)

                            # Compute aggregations if requested
                            if aggregations and messages:
                                message_aggregations = {}

                                if "count_by_user" in aggregations:
                                    user_counts = Counter(
                                        msg.get("sender_full_name", "Unknown")
                                        for msg in messages
                                    )
                                    message_aggregations["count_by_user"] = dict(
                                        user_counts.most_common(10)
                                    )

                                if "count_by_stream" in aggregations:
                                    stream_counts = Counter(
                                        msg.get("display_recipient", "Unknown")
                                        for msg in messages
                                    )
                                    message_aggregations["count_by_stream"] = dict(
                                        stream_counts.most_common(10)
                                    )

                                if "count_by_time" in aggregations:
                                    # Group by hour
                                    time_counts: dict[str, int] = {}
                                    for msg in messages:
                                        timestamp = datetime.fromtimestamp(
                                            msg.get("timestamp", 0)
                                        )
                                        hour_key = timestamp.strftime("%Y-%m-%d %H:00")
                                        time_counts[hour_key] = (
                                            time_counts.get(hour_key, 0) + 1
                                        )
                                    message_aggregations["count_by_time"] = dict(
                                        sorted(time_counts.items())
                                    )

                                if "word_frequency" in aggregations:
                                    word_freq: Counter[str] = Counter()
                                    for msg in messages:
                                        content = msg.get("content", "").lower()
                                        words = re.findall(r"\b[a-zA-Z]{3,}\b", content)
                                        word_freq.update(words)
                                    message_aggregations["word_frequency"] = dict(
                                        word_freq.most_common(20)
                                    )

                                if "emoji_usage" in aggregations:
                                    emoji_freq: Counter[str] = Counter()
                                    for msg in messages:
                                        reactions = msg.get("reactions", [])
                                        for reaction in reactions:
                                            emoji_name = reaction.get("emoji_name", "")
                                            emoji_freq[emoji_name] += len(
                                                reaction.get("user_ids", [])
                                            )
                                    message_aggregations["emoji_usage"] = dict(
                                        emoji_freq.most_common(10)
                                    )

                                results["aggregations"][
                                    "messages"
                                ] = message_aggregations

                    # Search users
                    if "users" in search_type:
                        try:
                            users_result = client.get_users(
                                {"client_gravatar": True}
                            )  # fakes may expect a request arg
                        except TypeError:
                            users_result = client.get_users()
                        if users_result.get("result") == "success":
                            all_users = users_result.get("members", [])
                            query_lower = query.lower()

                            # Filter users by query
                            matching_users = []
                            for user in all_users:
                                if (
                                    query_lower in user.get("full_name", "").lower()
                                    or query_lower in user.get("email", "").lower()
                                ):
                                    matching_users.append(user)

                            results["results"]["users"] = {
                                "count": len(matching_users),
                                "users": matching_users[:limit],
                                "has_more": len(matching_users) >= limit,
                            }
                            results["metadata"]["total_results"] += len(matching_users)

                    # Search streams
                    if "streams" in search_type:
                        try:
                            streams_result = client.get_streams(include_subscribed=True)
                        except TypeError:
                            try:
                                streams_result = client.get_streams()
                            except TypeError:
                                streams_result = client.get_streams(
                                    {"include_all_active": True}
                                )
                        if streams_result.get("result") == "success":
                            all_streams = streams_result.get("streams", [])
                            query_lower = query.lower()

                            # Filter streams by query
                            matching_streams = []
                            for stream in all_streams:
                                if (
                                    query_lower in stream.get("name", "").lower()
                                    or query_lower
                                    in stream.get("description", "").lower()
                                ):
                                    matching_streams.append(stream)

                            results["results"]["streams"] = {
                                "count": len(matching_streams),
                                "streams": matching_streams[:limit],
                                "has_more": len(matching_streams) >= limit,
                            }
                            results["metadata"]["total_results"] += len(
                                matching_streams
                            )

                    # Search topics (via stream messages)
                    if "topics" in search_type:
                        # Get recent topics from all streams
                        try:
                            streams_result = client.get_streams(include_subscribed=True)
                        except TypeError:
                            try:
                                streams_result = client.get_streams()
                            except TypeError:
                                streams_result = client.get_streams(
                                    {"include_all_active": True}
                                )
                        if streams_result.get("result") == "success":
                            all_streams = streams_result.get("streams", [])
                            matching_topics = []
                            query_lower = query.lower()

                            # Search topics in each stream (limited to prevent timeout)
                            for stream in all_streams[:20]:  # Limit stream search
                                topics_result = client.get_stream_topics(
                                    stream["stream_id"]
                                )
                                if topics_result.get("result") == "success":
                                    topics = topics_result.get("topics", [])
                                    for topic in topics:
                                        topic_name = topic.get("name", "")
                                        if query_lower in topic_name.lower():
                                            matching_topics.append(
                                                {
                                                    **topic,
                                                    "stream_name": stream["name"],
                                                    "stream_id": stream["stream_id"],
                                                }
                                            )

                            results["results"]["topics"] = {
                                "count": len(matching_topics),
                                "topics": matching_topics[:limit],
                                "has_more": len(matching_topics) >= limit,
                            }
                            results["metadata"]["total_results"] += len(matching_topics)

                    # Apply token limiting to prevent response size issues
                    results, was_truncated = truncate_for_tokens(results)
                    if was_truncated:
                        logger.info(f"Advanced search results truncated for query: '{query}'")

                    # Cache results if enabled
                    if use_cache:
                        _search_cache[cache_key] = results
                        # Simple cache cleanup - keep only last 100 entries
                        if len(_search_cache) > 100:
                            oldest_key = next(iter(_search_cache))
                            del _search_cache[oldest_key]

                    return results

                # Execute with identity management and error handling
                result = await identity_manager.execute_with_identity(
                    "search.advanced_search",
                    {"query": query},
                    _execute_search,
                    IdentityType.USER,  # Use user identity for search
                )

                logger.info(f"Advanced search completed for query: '{query}'")
                return result

            except Exception as e:
                error_msg = f"Failed to execute advanced search: {str(e)}"
                logger.error(error_msg)
                track_tool_error("search.advanced_search", str(e))

                return {"status": "error", "error": error_msg, "query": query}


async def get_daily_summary(
    streams: list[str] | None = None, hours_back: int = 24
) -> dict[str, Any]:
    """Get daily summary of messages across specified streams.

    This tool provides stream-specific daily activity summaries showing message counts,
    active users, and topic breakdowns for the specified time period.

    Args:
        streams: List of stream names to analyze. If None, analyzes all public streams.
        hours_back: Number of hours to look back (1-168 hours, defaults to 24).

    Returns:
        Daily summary with total messages, per-stream breakdowns, top senders,
        and topic activity for the specified time period.

    Examples:
        # Daily summary for specific streams
        await get_daily_summary(["general", "development"], hours_back=24)

        # Weekly summary for all public streams
        await get_daily_summary(hours_back=168)

        # Custom time period for project streams
        await get_daily_summary(["project-alpha", "project-beta"], hours_back=48)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "search.get_daily_summary"}):
        with LogContext(
            logger, tool="get_daily_summary", streams=streams, hours_back=hours_back
        ):
            track_tool_call("search.get_daily_summary")

            try:
                config, identity_manager, validator = _get_managers()

                # Validate hours_back parameter
                if not (1 <= hours_back <= 168):
                    return {
                        "status": "error",
                        "error": "hours_back must be between 1 and 168 hours",
                    }

                # Execute daily summary with appropriate identity and error handling
                async def _execute_daily_summary(
                    client: ZulipClientWrapper, params: dict[str, Any]
                ) -> dict[str, Any]:
                    # If no streams specified, get all public streams
                    target_streams = streams
                    if target_streams is None:
                        try:
                            streams_result = client.get_streams(include_subscribed=True)
                        except TypeError:
                            try:
                                streams_result = client.get_streams()
                            except TypeError:
                                streams_result = client.get_streams(
                                    {"include_all_active": True}
                                )
                        if streams_result.get("result") != "success":
                            return {
                                "status": "error",
                                "error": "Failed to fetch streams list",
                            }

                        # Filter to public streams only
                        all_streams = streams_result.get("streams", [])
                        target_streams = [
                            stream["name"]
                            for stream in all_streams
                            if not stream.get("invite_only", False)
                        ]

                    # Aggregation locals with precise types
                    total_messages: int = 0
                    streams_map: dict[str, dict[str, Any]] = {}
                    top_senders: dict[str, int] = {}

                    # Create time range filter
                    time_range = TimeRange(hours=hours_back)
                    time_filters = time_range.to_narrow_filters()

                    # Analyze each stream
                    for stream_name in target_streams:
                        # Build narrow filters for this stream using NarrowHelper
                        stream_narrow = [
                            NarrowHelper.stream(stream_name)
                        ] + time_filters
                        narrow_dict = NarrowHelper.to_api_format(stream_narrow)

                        # Get messages for this stream
                        # Use ZulipClientWrapper get_messages_raw with caching for daily summaries
                        message_result = client.get_messages_raw(
                            narrow=narrow_dict,
                            anchor="newest",
                            num_before=1000,  # Reasonable limit for daily summary
                            num_after=0,
                            include_anchor=True,
                            apply_markdown=False,  # Raw content for analysis
                            client_gravatar=False,
                        )

                        if message_result.get("result") != "success":
                            logger.warning(
                                f"Failed to get messages for stream {stream_name}"
                            )
                            continue

                        messages = message_result.get("messages", [])
                        message_count = len(messages)

                        # Initialize per-stream aggregates
                        topics_map: dict[str, int] = {}
                        active_users: set[str] = set()

                        # Process messages for this stream
                        for message in messages:
                            total_messages += 1

                            # Track senders across all streams
                            sender = message.get("sender_full_name", "Unknown")
                            top_senders[sender] = top_senders.get(sender, 0) + 1

                            # Track active users in this stream
                            active_users.add(sender)

                            # Track topics in this stream
                            topic = message.get("subject", "")
                            if topic:
                                topics_map[topic] = topics_map.get(topic, 0) + 1

                        # Store per-stream summary
                        streams_map[stream_name] = {
                            "message_count": message_count,
                            "topics": dict(
                                sorted(
                                    topics_map.items(), key=lambda x: x[1], reverse=True
                                )
                            ),
                            "active_user_count": len(active_users),
                            "topic_count": len(topics_map),
                        }

                    # Sort and limit top senders (top 10)
                    top_senders = dict(
                        sorted(top_senders.items(), key=lambda x: x[1], reverse=True)[
                            :10
                        ]
                    )

                    insights: dict[str, Any] = {}
                    if total_messages > 0:
                        active_streams = sum(
                            1 for s in streams_map.values() if s["message_count"] > 0
                        )
                        most_active = (
                            max(
                                streams_map.items(), key=lambda x: x[1]["message_count"]
                            )[0]
                            if streams_map
                            else None
                        )
                        insights = {
                            "most_active_stream": most_active,
                            "active_streams_count": active_streams,
                            "average_messages_per_active_stream": (
                                total_messages / active_streams
                                if active_streams > 0
                                else 0
                            ),
                            "total_unique_senders": len(top_senders),
                        }

                    summary_final = {
                        "status": "success",
                        "total_messages": total_messages,
                        "streams": streams_map,
                        "top_senders": top_senders,
                        "insights": insights,
                        "time_range": f"Last {hours_back} hours",
                        "analyzed_streams": len(target_streams or []),
                        "metadata": {
                            "analysis_time": datetime.now().isoformat(),
                            "hours_analyzed": hours_back,
                        },
                    }

                    return summary_final

                # Execute with identity management and error handling
                result = await identity_manager.execute_with_identity(
                    "search.get_daily_summary",
                    {"streams": streams, "hours_back": hours_back},
                    _execute_daily_summary,
                    IdentityType.USER,  # Use user identity for daily summary
                )

                logger.info(
                    f"Daily summary completed for {len(streams or [])} streams, {hours_back} hours back"
                )
                return result

            except Exception as e:
                error_msg = f"Failed to generate daily summary: {str(e)}"
                logger.error(error_msg)
                track_tool_error("search.get_daily_summary", str(e))

                return {
                    "status": "error",
                    "error": error_msg,
                    "streams": streams,
                    "hours_back": hours_back,
                }


async def analytics(
    metric: Literal["activity", "sentiment", "topics", "participation"],
    narrow: list[NarrowFilter] | None = None,
    group_by: Literal["user", "stream", "day", "hour"] | None = None,
    time_range: TimeRange | None = None,
    # Output options
    format: Literal["summary", "detailed", "chart_data"] = "summary",
    include_stats: bool = True,
) -> AnalyticsResponse:
    """Analytics and insights from message data.

    This tool provides comprehensive analytics and insights from Zulip message data
    including activity patterns, sentiment analysis, topic analysis, and participation metrics.

    Args:
        metric: Type of analytics to compute
        narrow: Narrow filters to limit data scope
        group_by: How to group the analytics data
        time_range: Time range for analysis (defaults to last 7 days)
        format: Output format for results
        include_stats: Whether to include statistical summaries

    Returns:
        AnalyticsResponse with computed metrics and insights

    Examples:
        # Activity analysis for last week
        await analytics("activity", time_range=TimeRange(days=7), group_by="day")

        # Sentiment analysis for specific stream
        narrow_filters = [NarrowFilter("stream", "general")]
        await analytics("sentiment", narrow=narrow_filters, format="detailed")

        # Topic analysis with chart data
        await analytics("topics", time_range=TimeRange(days=30), format="chart_data")

        # Participation metrics by user
        await analytics("participation", group_by="user", include_stats=True)
    """
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "search.analytics"}):
        with LogContext(logger, tool="analytics", metric=metric, group_by=group_by):
            track_tool_call("search.analytics")

            try:
                config, identity_manager, validator = _get_managers()

                # Default time range to last 7 days
                if time_range is None:
                    time_range = TimeRange(days=7)

                # Execute analytics with appropriate identity and error handling
                async def _execute_analytics(
                    client: ZulipClientWrapper, params: dict[str, Any]
                ) -> dict[str, Any]:
                    metadata: dict[str, Any] = {
                        "analysis_time": datetime.now().isoformat(),
                        "total_messages_analyzed": 0,
                    }
                    data_block: dict[str, Any] = {}
                    results: dict[str, Any] = {
                        "status": "success",
                        "metric": metric,
                        "time_range": {
                            "days": time_range.days,
                            "hours": time_range.hours,
                            "start": (
                                time_range.start.isoformat()
                                if time_range.start
                                else None
                            ),
                            "end": (
                                time_range.end.isoformat() if time_range.end else None
                            ),
                        },
                        "group_by": group_by,
                        "format": format,
                        "data": data_block,
                        "metadata": metadata,
                    }

                    # Build narrow filters for message retrieval
                    message_narrow = narrow or []
                    message_narrow.extend(time_range.to_narrow_filters())
                    narrow_dict = NarrowHelper.to_api_format(message_narrow)

                    # Get messages for analysis
                    # Use ZulipClientWrapper get_messages_raw for analytics
                    message_result = client.get_messages_raw(
                        narrow=narrow_dict,
                        anchor="newest",
                        num_before=1000,  # Limit for analysis
                        num_after=0,
                        include_anchor=True,
                        apply_markdown=False,  # Raw content for analysis
                        client_gravatar=False,
                    )

                    if message_result.get("result") != "success":
                        return {
                            "status": "error",
                            "error": f"Failed to retrieve messages: {message_result.get('msg', 'Unknown error')}",
                        }

                    messages = message_result.get("messages", [])
                    metadata["total_messages_analyzed"] = len(messages)

                    if not messages:
                        results["data"] = {
                            "message": "No messages found in the specified time range and filters"
                        }
                        return results

                    # Compute analytics based on metric type
                    if metric == "activity":
                        activity_data: dict[str, int] = {}

                        for message in messages:
                            timestamp = datetime.fromtimestamp(
                                message.get("timestamp", 0)
                            )

                            if group_by == "user":
                                key = message.get("sender_full_name", "Unknown")
                            elif group_by == "stream":
                                key = message.get("display_recipient", "Unknown")
                            elif group_by == "day":
                                key = timestamp.strftime("%Y-%m-%d")
                            elif group_by == "hour":
                                key = timestamp.strftime("%Y-%m-%d %H:00")
                            else:
                                key = "total"

                            activity_data[key] = activity_data.get(key, 0) + 1

                        results["data"]["activity"] = dict(
                            sorted(activity_data.items())
                        )

                        if include_stats:
                            values = list(activity_data.values())
                            results["data"]["statistics"] = {
                                "total_messages": sum(values),
                                "average": sum(values) / len(values) if values else 0,
                                "max": max(values) if values else 0,
                                "min": min(values) if values else 0,
                                "unique_contributors": len(activity_data),
                            }

                    elif metric == "sentiment":
                        sentiment_data: dict[str, list[dict[str, Any]]] = {}
                        overall_sentiment: dict[str, int] = {}

                        for message in messages:
                            content = message.get("content", "")
                            sentiment_analysis = _analyze_message_sentiment(content)
                            sentiment = sentiment_analysis["sentiment"]

                            overall_sentiment[sentiment] = (
                                overall_sentiment.get(sentiment, 0) + 1
                            )

                            if group_by == "user":
                                key = message.get("sender_full_name", "Unknown")
                            elif group_by == "stream":
                                key = message.get("display_recipient", "Unknown")
                            elif group_by == "day":
                                timestamp = datetime.fromtimestamp(
                                    message.get("timestamp", 0)
                                )
                                key = timestamp.strftime("%Y-%m-%d")
                            elif group_by == "hour":
                                timestamp = datetime.fromtimestamp(
                                    message.get("timestamp", 0)
                                )
                                key = timestamp.strftime("%Y-%m-%d %H:00")
                            else:
                                key = "overall"

                            sentiment_data.setdefault(key, []).append(
                                sentiment_analysis
                            )

                        # Aggregate sentiment by group
                        aggregated_sentiment: dict[str, dict[str, float | int]] = {}
                        for key, sentiments in sentiment_data.items():
                            positive = sum(
                                1 for s in sentiments if s["sentiment"] == "positive"
                            )
                            negative = sum(
                                1 for s in sentiments if s["sentiment"] == "negative"
                            )
                            neutral = sum(
                                1 for s in sentiments if s["sentiment"] == "neutral"
                            )
                            total = len(sentiments)

                            aggregated_sentiment[key] = {
                                "positive": positive,
                                "negative": negative,
                                "neutral": neutral,
                                "total": total,
                                "positive_ratio": positive / total if total > 0 else 0,
                                "negative_ratio": negative / total if total > 0 else 0,
                            }

                        results["data"]["sentiment"] = aggregated_sentiment
                        results["data"]["overall_distribution"] = dict(
                            overall_sentiment
                        )

                    elif metric == "topics":
                        topic_analysis = _extract_topics_from_messages(messages)
                        results["data"]["topics"] = topic_analysis

                        if group_by:
                            # Group topic analysis by specified dimension
                            grouped_topics = defaultdict(list)
                            for message in messages:
                                if group_by == "user":
                                    key = message.get("sender_full_name", "Unknown")
                                elif group_by == "stream":
                                    key = message.get("display_recipient", "Unknown")
                                elif group_by == "day":
                                    timestamp = datetime.fromtimestamp(
                                        message.get("timestamp", 0)
                                    )
                                    key = timestamp.strftime("%Y-%m-%d")
                                else:
                                    key = "all"

                                grouped_topics[key].append(message)

                            grouped_analysis = {}
                            for key, group_messages in grouped_topics.items():
                                grouped_analysis[key] = _extract_topics_from_messages(
                                    group_messages
                                )

                            results["data"]["grouped_topics"] = grouped_analysis

                    elif metric == "participation":
                        participation_data: dict[str, dict[str, Any]] = {}

                        for message in messages:
                            sender = message.get("sender_full_name", "Unknown")
                            content = message.get("content", "")
                            topic = message.get("subject", "")
                            stream = message.get("display_recipient", "")

                            if group_by == "user":
                                key = sender
                            elif group_by == "stream":
                                key = stream
                            elif group_by == "day":
                                timestamp = datetime.fromtimestamp(
                                    message.get("timestamp", 0)
                                )
                                key = timestamp.strftime("%Y-%m-%d")
                            else:
                                key = "overall"

                            entry = participation_data.setdefault(
                                key,
                                {
                                    "message_count": 0,
                                    "unique_topics": cast(set[str], set()),
                                    "unique_streams": cast(set[str], set()),
                                    "total_chars": 0,
                                },
                            )
                            entry["message_count"] = entry["message_count"] + 1
                            cast(set[str], entry["unique_topics"]).add(topic)
                            cast(set[str], entry["unique_streams"]).add(stream)
                            entry["total_chars"] = entry["total_chars"] + len(content)

                        # Convert sets to counts and calculate averages
                        processed_participation: dict[str, dict[str, float | int]] = {}
                        for key, data in participation_data.items():
                            msg_count = data["message_count"]
                            processed_participation[key] = {
                                "message_count": msg_count,
                                "unique_topics": len(data["unique_topics"]),
                                "unique_streams": len(data["unique_streams"]),
                                "avg_message_length": (
                                    data["total_chars"] / msg_count
                                    if msg_count > 0
                                    else 0
                                ),
                                "total_characters": data["total_chars"],
                            }

                        results["data"]["participation"] = processed_participation

                    # Format results based on requested format
                    if format == "chart_data":
                        results["chart_data"] = _convert_to_chart_format(
                            results["data"], metric, group_by
                        )
                    elif format == "detailed":
                        results["detailed_insights"] = _generate_detailed_insights(
                            results["data"], metric
                        )

                    return results

                # Execute with identity management and error handling
                result = await identity_manager.execute_with_identity(
                    "search.analytics",
                    {"metric": metric},
                    _execute_analytics,
                    IdentityType.USER,  # Use user identity for analytics
                )

                logger.info(f"Analytics completed for metric: {metric}")
                return result

            except Exception as e:
                error_msg = f"Failed to execute analytics: {str(e)}"
                logger.error(error_msg)
                track_tool_error("search.analytics", str(e))

                return {"status": "error", "error": error_msg, "metric": metric}


def _convert_to_chart_format(
    data: dict[str, Any], metric: str, group_by: str | None
) -> dict[str, Any]:
    """Convert analytics data to chart-friendly format."""
    chart_data: dict[str, Any] = {"type": metric, "group_by": group_by, "series": []}

    if metric == "activity" and "activity" in data:
        chart_data["series"] = [
            {"name": key, "value": value} for key, value in data["activity"].items()
        ]
    elif metric == "sentiment" and "sentiment" in data:
        for group, sentiment_info in data["sentiment"].items():
            chart_data["series"].append(
                {
                    "name": group,
                    "positive": sentiment_info["positive"],
                    "negative": sentiment_info["negative"],
                    "neutral": sentiment_info["neutral"],
                }
            )
    elif metric == "participation" and "participation" in data:
        chart_data["series"] = [
            {
                "name": key,
                "messages": value["message_count"],
                "engagement": value["unique_topics"],
            }
            for key, value in data["participation"].items()
        ]

    return chart_data


def _generate_detailed_insights(data: dict[str, Any], metric: str) -> list[str]:
    """Generate human-readable insights from analytics data."""
    insights = []

    if metric == "activity" and "activity" in data and "statistics" in data:
        stats = data["statistics"]
        insights.append(f"Total messages analyzed: {stats['total_messages']}")
        insights.append(f"Average activity level: {stats['average']:.1f} messages")
        insights.append(f"Most active contributor sent {stats['max']} messages")
        insights.append(
            f"Activity spread across {stats['unique_contributors']} contributors"
        )

    elif metric == "sentiment" and "overall_distribution" in data:
        total = sum(data["overall_distribution"].values())
        positive_pct = (
            (data["overall_distribution"].get("positive", 0) / total) * 100
            if total > 0
            else 0
        )
        negative_pct = (
            (data["overall_distribution"].get("negative", 0) / total) * 100
            if total > 0
            else 0
        )

        insights.append(
            f"Overall sentiment: {positive_pct:.1f}% positive, {negative_pct:.1f}% negative"
        )

        if positive_pct > 60:
            insights.append("Generally positive communication tone detected")
        elif negative_pct > 30:
            insights.append(
                "Notable negative sentiment detected - may warrant attention"
            )

    elif metric == "topics" and "topics" in data:
        topic_dist = data["topics"]["topic_distribution"]
        if topic_dist:
            top_topic = max(topic_dist.items(), key=lambda x: x[1])
            insights.append(
                f"Most discussed topic: {top_topic[0]} ({top_topic[1]} mentions)"
            )

        top_words = data["topics"]["top_words"][:5]
        if top_words:
            word_list = ", ".join([f"{word}({count})" for word, count in top_words])
            insights.append(f"Most frequent words: {word_list}")

    elif metric == "participation" and "participation" in data:
        participation = data["participation"]
        if "overall" in participation:
            overall = participation["overall"]
            insights.append(
                f"Average message length: {overall['avg_message_length']:.1f} characters"
            )
            insights.append(
                f"Discussion spans {overall['unique_topics']} topics across {overall['unique_streams']} streams"
            )

    return insights


def register_search_v25_tools(mcp: Any) -> None:
    """Register all search v2.5 tools with the MCP server.

    Args:
        mcp: FastMCP instance to register tools on
    """
    mcp.tool(description="Multi-faceted search across Zulip with intelligent result ranking and aggregation. Search messages (default), users, streams, or topics with powerful filtering, time ranges, and content analysis. Supports search aggregations and statistical insights. Results automatically truncated to fit token limits while preserving key information.")(advanced_search)
    mcp.tool(description="Generate analytics and insights from message data including activity patterns, sentiment analysis, topic modeling, user participation metrics, and trend analysis. Supports time-range filtering and multiple analytical metrics. Provides actionable insights for community management and engagement optimization.")(analytics)
    mcp.tool(description="Generate comprehensive daily activity summary showing message counts, active users, popular topics, and stream engagement metrics across specified time period. Aggregates data from multiple streams with activity ranking and participation analysis. Ideal for community management dashboards.")(get_daily_summary)
