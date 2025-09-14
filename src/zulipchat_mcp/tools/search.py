"""Search tools for ZulipChat MCP v2.5.1.

Complete search operations including advanced search, analytics, user resolution,
and aggregations. All functionality from the complex v25 architecture preserved.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Literal

from fastmcp import FastMCP

from ..client import ZulipClientWrapper
from ..config import ConfigManager


class UserResolutionError(Exception):
    """Base class for user resolution errors."""
    pass


class AmbiguousUserError(UserResolutionError):
    """Raised when user identifier matches multiple users."""

    def __init__(self, identifier: str, matches: list[dict[str, Any]]):
        self.identifier = identifier
        self.matches = matches
        match_strings = [f"{m.get('full_name')} ({m.get('email')})" for m in matches]
        super().__init__(f"Multiple matches for '{identifier}': {', '.join(match_strings[:5])}")


class UserNotFoundError(UserResolutionError):
    """Raised when user identifier cannot be resolved."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"No user matching '{identifier}'")


async def resolve_user_identifier(identifier: str, client: ZulipClientWrapper) -> dict[str, Any]:
    """Resolve partial names, emails, or IDs to full user info.

    Handles fuzzy matching for cases like 'Jaime' -> 'jcernudagarcia@hawk.iit.edu'
    """
    try:
        # Try exact email match first
        if "@" in identifier:
            response = client.get_users()
            if response.get("result") == "success":
                users = response.get("members", [])
                exact_match = next(
                    (user for user in users if user.get("email") == identifier), None
                )
                if exact_match:
                    return exact_match

        # Get all users for fuzzy matching
        response = client.get_users()
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

        # Fuzzy matching with similarity scoring
        partial_matches = []
        for user in users:
            full_name = user.get("full_name", "")
            if (
                identifier.lower() in full_name.lower()
                or SequenceMatcher(None, full_name.lower(), identifier.lower()).ratio() > 0.6
            ):
                score = SequenceMatcher(None, full_name.lower(), identifier.lower()).ratio()
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
                user for score, user in partial_matches
                if score > best_score - 0.2
            ]
            if len(close_matches) == 1:
                return close_matches[0]
            else:
                raise AmbiguousUserError(identifier, close_matches[:5])

    except (AmbiguousUserError, UserNotFoundError):
        raise
    except Exception as e:
        raise Exception(f"Failed to resolve user '{identifier}': {str(e)}")


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
) -> list[dict[str, str]]:
    """Build comprehensive narrow filter for Zulip API."""
    narrow = []

    # Basic filters
    if stream:
        narrow.append({"operator": "stream", "operand": stream})
    if topic:
        narrow.append({"operator": "topic", "operand": topic})
    if sender:
        narrow.append({"operator": "sender", "operand": sender})
    if text:
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

    # Time filters (priority order)
    if last_hours:
        hours = int(last_hours) if isinstance(last_hours, str) else last_hours
        cutoff_time = datetime.now() - timedelta(hours=hours)
        narrow.append({"operator": "search", "operand": f"after:{cutoff_time.isoformat()}"})
    elif last_days:
        days = int(last_days) if isinstance(last_days, str) else last_days
        cutoff_time = datetime.now() - timedelta(days=days)
        narrow.append({"operator": "search", "operand": f"after:{cutoff_time.isoformat()}"})
    elif after_time:
        time_str = after_time.isoformat() if isinstance(after_time, datetime) else after_time
        narrow.append({"operator": "search", "operand": f"after:{time_str}"})

    if before_time:
        time_str = before_time.isoformat() if isinstance(before_time, datetime) else before_time
        narrow.append({"operator": "search", "operand": f"before:{time_str}"})

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
    highlight: bool = True,
) -> dict[str, Any]:
    """Advanced search with fuzzy user resolution and comprehensive filtering."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

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
                        "suggestions": [f"Did you mean: {m.get('full_name')} ({m.get('email')})?" for m in e.matches[:3]],
                        "recovery": {"tool": "list_users", "hint": "List users to see all available options"}
                    }
                }
            except UserNotFoundError as e:
                return {
                    "status": "error",
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": str(e),
                        "suggestions": ["Use full email address", "Check spelling", "Use list_users to see available users"],
                        "recovery": {"tool": "list_users", "hint": "Search users to find correct identifier"}
                    }
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": {
                        "code": "USER_RESOLUTION_FAILED",
                        "message": f"Could not resolve user '{sender}': {str(e)}",
                        "suggestions": ["Use full email address", "Try a different identifier"]
                    }
                }

        # Build narrow filter
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
            last_hours=last_hours,
            last_days=last_days,
            after_time=after_time,
            before_time=before_time,
        )

        # Execute search
        anchor = "newest" if sort_by == "newest" else "oldest"
        result = client.get_messages_raw(
            anchor=anchor,
            narrow=narrow,
            num_before=limit,
            include_anchor=True,
            client_gravatar=True,
            apply_markdown=True,
        )

        if result.get("result") == "success":
            messages = result.get("messages", [])

            # Process messages for response
            processed_messages = []
            for msg in messages:
                processed_messages.append({
                    "id": msg["id"],
                    "sender": msg["sender_full_name"],
                    "email": msg["sender_email"],
                    "timestamp": msg["timestamp"],
                    "content": msg["content"][:1000] + "..." if len(msg["content"]) > 1000 else msg["content"],
                    "type": msg["type"],
                    "stream": msg.get("display_recipient"),
                    "topic": msg.get("subject"),
                    "reactions": msg.get("reactions", []),
                    "flags": msg.get("flags", []),
                })

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
    highlight: bool = True,
    # Analytics
    aggregations: list[str] | None = None,
) -> dict[str, Any]:
    """Multi-faceted search with aggregations and analytics."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

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
            users_response = client.get_users()
            if users_response.get("result") == "success":
                users = users_response.get("members", [])
                matching_users = [
                    user for user in users
                    if query.lower() in user.get("full_name", "").lower()
                    or query.lower() in user.get("email", "").lower()
                ][:limit]
                results["users"] = {"status": "success", "users": matching_users, "count": len(matching_users)}

        # Search streams
        if "streams" in search_type:
            streams_response = client.get_streams()
            if streams_response.get("result") == "success":
                streams = streams_response.get("streams", [])
                matching_streams = [
                    stream for stream in streams
                    if query.lower() in stream.get("name", "").lower()
                    or query.lower() in stream.get("description", "").lower()
                ][:limit]
                results["streams"] = {"status": "success", "streams": matching_streams, "count": len(matching_streams)}

        # Aggregations
        if aggregations and "messages" in results and results["messages"].get("status") == "success":
            messages = results["messages"].get("messages", [])
            agg_results = {}

            if "count_by_user" in aggregations:
                user_counts = Counter(msg["sender"] for msg in messages)
                agg_results["count_by_user"] = dict(user_counts.most_common(10))

            if "count_by_stream" in aggregations:
                stream_counts = Counter(msg["stream"] for msg in messages if msg["stream"])
                agg_results["count_by_stream"] = dict(stream_counts.most_common(10))

            if "word_frequency" in aggregations:
                # Simple word frequency analysis
                all_content = " ".join(msg["content"] for msg in messages)
                words = re.findall(r'\b\w+\b', all_content.lower())
                word_freq = Counter(words)
                # Filter common words
                common_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they"}
                filtered_words = {word: count for word, count in word_freq.items() if word not in common_words and len(word) > 2}
                agg_results["word_frequency"] = dict(Counter(filtered_words).most_common(20))

            results["aggregations"] = agg_results

        return {
            "status": "success",
            "query": query,
            "search_types": search_type,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "query": query}


async def analytics(
    metric: Literal["activity", "sentiment", "topics", "participation"],
    # Filters
    stream: str | None = None,
    sender: str | None = None,
    # Time range
    last_hours: int | None = None,
    last_days: int | None = None,
    # Response format
    format: Literal["summary", "detailed", "chart_data"] = "summary",
    group_by: Literal["user", "stream", "day", "hour"] | None = None,
) -> dict[str, Any]:
    """Generate analytics and insights from message data."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Get messages for analysis
        search_result = await search_messages(
            stream=stream,
            sender=sender,
            last_hours=last_hours,
            last_days=last_days,
            limit=500,  # Larger sample for analytics
        )

        if search_result.get("status") != "success":
            return {"status": "error", "error": "Failed to get messages for analytics"}

        messages = search_result.get("messages", [])

        if not messages:
            return {"status": "success", "metric": metric, "data": {}, "message": "No messages found for analysis"}

        # Perform analytics based on metric type
        if metric == "activity":
            # Activity metrics
            data = {
                "total_messages": len(messages),
                "unique_senders": len(set(msg["sender"] for msg in messages)),
                "streams_active": len(set(msg["stream"] for msg in messages if msg["stream"])),
                "avg_message_length": sum(len(msg["content"]) for msg in messages) / len(messages),
            }

            if group_by == "user":
                user_activity = Counter(msg["sender"] for msg in messages)
                data["by_user"] = dict(user_activity.most_common(10))
            elif group_by == "stream":
                stream_activity = Counter(msg["stream"] for msg in messages if msg["stream"])
                data["by_stream"] = dict(stream_activity.most_common(10))

        elif metric == "topics":
            # Topic analysis
            topics = [msg["topic"] for msg in messages if msg["topic"]]
            topic_counts = Counter(topics)
            data = {
                "total_topics": len(set(topics)),
                "most_active_topics": dict(topic_counts.most_common(10)),
                "avg_messages_per_topic": len(messages) / len(set(topics)) if topics else 0,
            }

        elif metric == "participation":
            # Participation metrics
            sender_counts = Counter(msg["sender"] for msg in messages)
            total_messages = len(messages)
            data = {
                "total_participants": len(sender_counts),
                "participation_distribution": {
                    sender: {"count": count, "percentage": (count / total_messages) * 100}
                    for sender, count in sender_counts.most_common(10)
                },
                "gini_coefficient": _calculate_gini_coefficient(list(sender_counts.values())),
            }

        else:  # sentiment
            # Basic sentiment analysis (simplified)
            positive_words = {"good", "great", "excellent", "awesome", "fantastic", "love", "like", "thanks", "thank", "perfect", "wonderful", "amazing"}
            negative_words = {"bad", "terrible", "awful", "hate", "dislike", "wrong", "error", "problem", "issue", "broken", "failed", "fail"}

            sentiment_scores = []
            for msg in messages:
                content_lower = msg["content"].lower()
                positive_count = sum(1 for word in positive_words if word in content_lower)
                negative_count = sum(1 for word in negative_words if word in content_lower)
                score = positive_count - negative_count
                sentiment_scores.append(score)

            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            data = {
                "average_sentiment": avg_sentiment,
                "positive_messages": len([s for s in sentiment_scores if s > 0]),
                "negative_messages": len([s for s in sentiment_scores if s < 0]),
                "neutral_messages": len([s for s in sentiment_scores if s == 0]),
                "sentiment_distribution": {
                    "positive": (len([s for s in sentiment_scores if s > 0]) / len(sentiment_scores)) * 100,
                    "negative": (len([s for s in sentiment_scores if s < 0]) / len(sentiment_scores)) * 100,
                    "neutral": (len([s for s in sentiment_scores if s == 0]) / len(sentiment_scores)) * 100,
                }
            }

        return {
            "status": "success",
            "metric": metric,
            "format": format,
            "data": data,
            "sample_size": len(messages),
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "metric": metric}


def _calculate_gini_coefficient(values: list[int]) -> float:
    """Calculate Gini coefficient for participation distribution."""
    if not values:
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)
    total = sum(sorted_values)

    if total == 0:
        return 0.0

    cumsum = 0
    for i, value in enumerate(sorted_values):
        cumsum += value
        # Gini coefficient formula

    # Simplified calculation
    return (2 * sum((i + 1) * value for i, value in enumerate(sorted_values))) / (n * total) - (n + 1) / n


async def get_daily_summary(
    streams: list[str] | None = None,
    hours_back: int = 24,
) -> dict[str, Any]:
    """Get daily message summary with comprehensive activity stats."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    summary = client.get_daily_summary(streams=streams, hours_back=hours_back)

    # Enhance with additional analytics
    if isinstance(summary, dict) and "streams" in summary:
        # Add engagement metrics
        total_topics = sum(len(stream_data.get("topics", {})) for stream_data in summary["streams"].values())
        active_streams = len([s for s, data in summary["streams"].items() if data.get("message_count", 0) > 0])

        summary["engagement_metrics"] = {
            "total_topics": total_topics,
            "active_streams": active_streams,
            "avg_messages_per_stream": summary["total_messages"] / max(active_streams, 1),
            "avg_topics_per_stream": total_topics / max(active_streams, 1),
        }

    return {
        "status": "success",
        "summary": summary,
        "generated_at": datetime.now().isoformat(),
        "time_range": f"Last {hours_back} hours",
    }


def register_search_tools(mcp: FastMCP) -> None:
    """Register search tools with the MCP server."""
    mcp.tool(name="search_messages", description="Advanced search with fuzzy user matching and comprehensive filtering")(search_messages)
    mcp.tool(name="advanced_search", description="Multi-faceted search across messages, users, streams with aggregations")(advanced_search)
    mcp.tool(name="analytics", description="Generate analytics and insights from message data")(analytics)
    mcp.tool(name="get_daily_summary", description="Get daily activity summary with engagement metrics")(get_daily_summary)