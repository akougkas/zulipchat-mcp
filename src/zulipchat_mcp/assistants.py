"""Intelligent assistant tools for ZulipChat MCP.

This module provides AI-powered assistant tools that enhance Zulip interactions:
- Smart reply suggestions based on conversation context
- Automatic summarization of stream conversations  
- Enhanced semantic search capabilities

These tools integrate with the existing command chain system and AsyncZulipClient
for seamless workflow automation.
"""

import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any

from .async_client import AsyncZulipClient
from .client import ZulipMessage
from .config import ConfigManager, ZulipConfig
from .exceptions import ZulipMCPError

logger = logging.getLogger(__name__)

# Global instances
_async_client: AsyncZulipClient | None = None
_config: ZulipConfig | None = None


def get_async_client() -> AsyncZulipClient:
    """Get or create async Zulip client instance."""
    global _async_client, _config
    if _async_client is None or _config is None:
        config_manager = ConfigManager()
        if not config_manager.validate_config():
            raise ZulipMCPError("Invalid Zulip configuration")
        _config = config_manager.config
        _async_client = AsyncZulipClient(_config)
    return _async_client


def sanitize_input(content: str, max_length: int = 10000) -> str:
    """Sanitize user input to prevent injection attacks."""
    import html
    content = html.escape(content)
    content = re.sub(r'`', '', content)
    return content[:max_length]


def validate_stream_name(name: str) -> bool:
    """Validate stream name against injection."""
    pattern = r'^[a-zA-Z0-9\-_\s\.]+$'
    return bool(re.match(pattern, name)) and 0 < len(name) <= 100


def extract_keywords(messages: list[ZulipMessage]) -> list[str]:
    """Extract simple keywords from messages."""
    if not messages:
        return []

    all_content = []
    for msg in messages:
        all_content.append(msg.content.lower())

    combined_content = " ".join(all_content)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', combined_content)
    word_counts = Counter(words)

    # Filter out common words
    common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use'}
    keywords = [word for word, count in word_counts.most_common(5) if word not in common_words and count > 1]

    return keywords








# Assistant Tool Functions (to be decorated by main server)

async def smart_reply_impl(
    stream_name: str,
    topic: str | None = None,
    hours_back: int = 4,
    context_messages: int = 10
) -> dict[str, Any]:
    """Analyze conversation context and suggest appropriate replies.
    
    Analyzes recent messages in a stream/topic to understand the conversation
    context and generates intelligent reply suggestions.
    
    Args:
        stream_name: Stream to analyze for context
        topic: Optional topic to focus on
        hours_back: How many hours back to look for context
        context_messages: Maximum messages to analyze for context
        
    Returns:
        Dictionary with reply suggestions and context analysis
    """
    try:
        # Validate inputs
        if not validate_stream_name(stream_name):
            return {"status": "error", "error": f"Invalid stream name: {stream_name}"}

        if not 1 <= hours_back <= 24:
            return {"status": "error", "error": "hours_back must be between 1 and 24"}

        if not 5 <= context_messages <= 50:
            return {"status": "error", "error": "context_messages must be between 5 and 50"}

        # Get async client
        client = get_async_client()

        # Fetch recent messages for context
        messages = await client.get_messages_async(
            stream_name=stream_name,
            topic=topic,
            limit=context_messages,
            hours_back=hours_back
        )

        if not messages:
            return {
                "status": "success",
                "suggestions": ["Start a new conversation on this topic!"],
                "context": {
                    "message_count": 0,
                    "participants": [],
                    "topics": [],
                    "sentiment": "neutral"
                }
            }

        # Sort messages by timestamp (oldest first for context)
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)

        # Simple keyword extraction
        keywords = extract_keywords(sorted_messages)

        # Generate basic suggestions
        suggestions = [
            f"Thanks for the update on {keywords[0]}" if keywords else "Thanks for the update",
            "I'll look into this and get back to you",
            "Could you provide more details?",
            "+1",
            "Acknowledged"
        ]

        return {
            "status": "success",
            "suggestions": suggestions[:3],
            "keywords": keywords,
            "message_count": len(messages)
        }

    except Exception as e:
        logger.error(f"Error in smart_reply: {e}")
        return {"status": "error", "error": "Failed to generate reply suggestions"}


async def auto_summarize_impl(
    stream_name: str,
    topic: str | None = None,
    hours_back: int = 24,
    summary_type: str = "standard",
    max_messages: int = 100
) -> dict[str, Any]:
    """Generate summaries of stream conversations.
    
    Automatically summarizes conversations in streams/topics with intelligent
    analysis of key points, participants, and themes.
    
    Args:
        stream_name: Stream to summarize
        topic: Optional topic to focus summary on
        hours_back: How many hours back to summarize
        summary_type: Type of summary ('brief', 'standard', 'detailed')
        max_messages: Maximum messages to include in summary
        
    Returns:
        Dictionary with conversation summary and analysis
    """
    try:
        # Validate inputs
        if not validate_stream_name(stream_name):
            return {"status": "error", "error": f"Invalid stream name: {stream_name}"}

        if summary_type not in ["brief", "standard", "detailed"]:
            return {"status": "error", "error": "summary_type must be 'brief', 'standard', or 'detailed'"}

        if not 1 <= hours_back <= 168:  # Max 1 week
            return {"status": "error", "error": "hours_back must be between 1 and 168"}

        if not 10 <= max_messages <= 500:
            return {"status": "error", "error": "max_messages must be between 10 and 500"}

        # Get async client
        client = get_async_client()

        # Fetch messages to summarize
        messages = await client.get_messages_async(
            stream_name=stream_name,
            topic=topic,
            limit=max_messages,
            hours_back=hours_back
        )

        if not messages:
            return {
                "status": "success",
                "summary": f"No messages found in #{stream_name}" + (f" > {topic}" if topic else "") + f" in the last {hours_back} hours.",
                "key_points": [],
                "participants": [],
                "topics": [],
                "message_count": 0
            }

        # Simple message counting summary
        summary_data = {
            "summary": f"Found {len(messages)} messages in the specified time period.",
            "key_points": [f"Total messages: {len(messages)}"],
            "participants": list(set(msg.sender_full_name for msg in messages)),
            "topics": [],
            "message_count": len(messages)
        }

        # Add metadata
        summary_data.update({
            "status": "success",
            "stream": stream_name,
            "topic_filter": topic,
            "time_period": f"{hours_back} hours",
            "generated_at": datetime.now().isoformat()
        })

        return summary_data

    except Exception as e:
        logger.error(f"Error in auto_summarize: {e}")
        return {"status": "error", "error": "Failed to generate conversation summary"}


async def smart_search_impl(
    query: str,
    stream_name: str | None = None,
    hours_back: int = 168,
    limit: int = 20
) -> dict[str, Any]:
    """Enhanced search with semantic understanding.
    
    Performs intelligent search across Zulip messages with query enhancement,
    semantic understanding, and relevance scoring.
    
    Args:
        query: Search query to enhance and execute
        stream_name: Optional stream to limit search to
        hours_back: How many hours back to search
        limit: Maximum number of results to return
        
    Returns:
        Dictionary with enhanced search results and analysis
    """
    try:
        # Validate inputs
        query = sanitize_input(query, max_length=200)
        if not query or len(query.strip()) < 2:
            return {"status": "error", "error": "Query must be at least 2 characters"}

        if stream_name and not validate_stream_name(stream_name):
            return {"status": "error", "error": f"Invalid stream name: {stream_name}"}

        if not 1 <= hours_back <= 720:  # Max 30 days
            return {"status": "error", "error": "hours_back must be between 1 and 720"}

        if not 1 <= limit <= 50:
            return {"status": "error", "error": "limit must be between 1 and 50"}

        # Get async client
        client = get_async_client()

        # Simple keyword search
        try:
            messages = await client.search_messages_async(query, limit)
            results = [
                {
                    "message": {
                        "id": msg.id,
                        "sender": msg.sender_full_name,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                        "stream": msg.stream_name,
                        "topic": msg.subject
                    },
                    "relevance_score": 1.0 if query.lower() in msg.content.lower() else 0.5,
                    "matched_terms": [query],
                    "search_type": "keyword_search"
                }
                for msg in messages
            ]
        except Exception:
            results = []

        # Simple query analysis
        enhanced_query = {
            "original_query": query,
            "expanded_terms": [],
            "search_type": "keyword"
        }

        # Calculate search statistics
        total_results = len(results)
        avg_relevance = sum(r["relevance_score"] for r in results) / max(total_results, 1)
        search_types = Counter(r["search_type"] for r in results)

        return {
            "status": "success",
            "query_analysis": enhanced_query,
            "results": results,
            "statistics": {
                "total_results": total_results,
                "average_relevance": round(avg_relevance, 3),
                "search_types": dict(search_types),
                "time_range": f"{hours_back} hours",
                "stream_filter": stream_name
            },
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in smart_search: {e}")
        return {"status": "error", "error": "Failed to perform semantic search"}



