"""Intelligent assistant tools for ZulipChat MCP.

This module provides AI-powered assistant tools that enhance Zulip interactions:
- Smart reply suggestions based on conversation context
- Automatic summarization of stream conversations  
- Enhanced semantic search capabilities

These tools integrate with the existing command chain system and AsyncZulipClient
for seamless workflow automation.
"""

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any

from .async_client import AsyncZulipClient
from .client import ZulipMessage
from .commands import CommandChain, ProcessDataCommand
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
        _config = config_manager.config.zulip
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


class ConversationAnalyzer:
    """Analyzes conversation context to provide intelligent suggestions."""

    @staticmethod
    def extract_conversation_context(messages: list[ZulipMessage]) -> dict[str, Any]:
        """Extract key context from conversation messages.
        
        Args:
            messages: List of messages to analyze
            
        Returns:
            Dictionary containing conversation context
        """
        if not messages:
            return {"topics": [], "participants": [], "sentiment": "neutral", "keywords": [], "message_count": 0, "time_span_hours": 0}

        # Extract topics, participants, and keywords
        topics = []
        participants = set()
        all_content = []

        for msg in messages:
            if msg.subject:
                topics.append(msg.subject)
            participants.add(msg.sender_full_name)
            all_content.append(msg.content.lower())

        # Find most common topics
        topic_counts = Counter(topics)
        top_topics = [topic for topic, _ in topic_counts.most_common(3)]

        # Extract keywords (simple approach - can be enhanced with NLP)
        combined_content = " ".join(all_content)
        # Remove common words and extract meaningful terms
        words = re.findall(r'\b[a-zA-Z]{3,}\b', combined_content)
        word_counts = Counter(words)
        # Filter out common words
        common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use'}
        keywords = [word for word, count in word_counts.most_common(10) if word not in common_words and count > 1]

        # Simple sentiment analysis based on keywords
        positive_indicators = ['good', 'great', 'excellent', 'awesome', 'perfect', 'thanks', 'thank']
        negative_indicators = ['bad', 'terrible', 'awful', 'wrong', 'error', 'problem', 'issue']
        question_indicators = ['how', 'what', 'when', 'where', 'why', 'which', '?']

        sentiment = "neutral"
        if any(word in combined_content for word in positive_indicators):
            sentiment = "positive"
        elif any(word in combined_content for word in negative_indicators):
            sentiment = "negative"
        elif any(word in combined_content for word in question_indicators):
            sentiment = "inquisitive"

        return {
            "topics": top_topics,
            "participants": list(participants),
            "sentiment": sentiment,
            "keywords": keywords,
            "message_count": len(messages),
            "time_span_hours": (messages[0].timestamp - messages[-1].timestamp) / 3600 if len(messages) > 1 else 0
        }

    @staticmethod
    def generate_reply_suggestions(context: dict[str, Any], latest_message: ZulipMessage) -> list[str]:
        """Generate intelligent reply suggestions based on context.
        
        Args:
            context: Conversation context from extract_conversation_context
            latest_message: The most recent message to respond to
            
        Returns:
            List of suggested reply texts
        """
        suggestions = []
        content = latest_message.content.lower()
        sender = latest_message.sender_full_name
        sentiment = context.get("sentiment", "neutral")
        keywords = context.get("keywords", [])

        # Question detection and responses
        if '?' in content or any(q in content for q in ['how', 'what', 'when', 'where', 'why', 'which']):
            suggestions.extend([
                f"Great question, {sender}! Let me think about that...",
                "I'd be happy to help with that. Here's what I think...",
                "That's an interesting point. Based on my experience..."
            ])

        # Problem/issue detection
        elif any(word in content for word in ['problem', 'issue', 'error', 'bug', 'help', 'stuck']):
            suggestions.extend([
                f"Sorry to hear you're having trouble, {sender}. Have you tried...",
                "I've seen similar issues before. One approach that works is...",
                "Let's troubleshoot this together. First, can you confirm..."
            ])

        # Positive sentiment responses
        elif sentiment == "positive" or any(word in content for word in ['thanks', 'great', 'awesome', 'perfect']):
            suggestions.extend([
                f"Glad to help, {sender}! 😊",
                "You're very welcome! Happy to assist.",
                "Excellent! Let me know if you need anything else."
            ])

        # Technical discussion detection
        elif any(word in keywords for word in ['code', 'api', 'function', 'database', 'server', 'bug', 'feature']):
            suggestions.extend([
                "That's a good technical point. In my experience...",
                "From a development perspective, I'd suggest...",
                "Have you considered the performance implications of..."
            ])

        # Meeting/planning detection
        elif any(word in content for word in ['meeting', 'schedule', 'plan', 'deadline', 'project']):
            suggestions.extend([
                "Thanks for the update! When do we need this completed?",
                "Good point about the timeline. Should we schedule a follow-up?",
                "I can help coordinate this. What's our next step?"
            ])

        # Default contextual responses
        if not suggestions:
            if context.get("topics"):
                main_topic = context["topics"][0]
                suggestions.append(f"Regarding {main_topic}, I think we should consider...")

            suggestions.extend([
                f"Thanks for sharing that, {sender}. My thoughts...",
                "That's an interesting perspective. I'd add that...",
                "Building on what you said..."
            ])

        # Ensure we have at least 3 suggestions
        while len(suggestions) < 3:
            suggestions.append("I appreciate your input on this topic.")

        return suggestions[:5]  # Return top 5 suggestions


class ConversationSummarizer:
    """Generates intelligent summaries of stream conversations."""

    @staticmethod
    def generate_summary(
        messages: list[ZulipMessage],
        summary_type: str = "standard",
        max_length: int = 500
    ) -> dict[str, Any]:
        """Generate a summary of conversation messages.
        
        Args:
            messages: List of messages to summarize
            summary_type: Type of summary ('standard', 'brief', 'detailed')
            max_length: Maximum summary length in characters
            
        Returns:
            Dictionary containing summary and metadata
        """
        if not messages:
            return {
                "summary": "No messages to summarize.",
                "key_points": [],
                "participants": [],
                "topics": [],
                "message_count": 0
            }

        # Sort messages by timestamp
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)

        # Extract context
        context = ConversationAnalyzer.extract_conversation_context(sorted_messages)

        # Generate summary based on type
        if summary_type == "brief":
            summary = ConversationSummarizer._generate_brief_summary(sorted_messages, context)
        elif summary_type == "detailed":
            summary = ConversationSummarizer._generate_detailed_summary(sorted_messages, context)
        else:
            summary = ConversationSummarizer._generate_standard_summary(sorted_messages, context)

        # Truncate if needed
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."

        # Extract key points
        key_points = ConversationSummarizer._extract_key_points(sorted_messages, context)

        return {
            "summary": summary,
            "key_points": key_points,
            "participants": context["participants"],
            "topics": context["topics"],
            "message_count": len(sorted_messages),
            "time_span": f"{context['time_span_hours']:.1f} hours",
            "sentiment": context["sentiment"]
        }

    @staticmethod
    def _generate_brief_summary(messages: list[ZulipMessage], context: dict[str, Any]) -> str:
        """Generate a brief summary (1-2 sentences)."""
        participants = context["participants"]
        topics = context["topics"]
        sentiment = context["sentiment"]

        participant_text = f"{len(participants)} participants" if len(participants) > 2 else " and ".join(participants)
        topic_text = f"discussing {', '.join(topics[:2])}" if topics else "in general discussion"

        sentiment_modifier = {
            "positive": "productive",
            "negative": "challenging",
            "inquisitive": "question-focused",
            "neutral": "informative"
        }.get(sentiment, "general")

        return f"{participant_text} had a {sentiment_modifier} conversation {topic_text} with {len(messages)} messages."

    @staticmethod
    def _generate_standard_summary(messages: list[ZulipMessage], context: dict[str, Any]) -> str:
        """Generate a standard summary (3-4 sentences)."""
        participants = context["participants"]
        topics = context["topics"]
        keywords = context["keywords"]

        # Introduction
        summary = f"Conversation involved {len(participants)} participants: {', '.join(participants[:3])}{'...' if len(participants) > 3 else ''}. "

        # Topics
        if topics:
            summary += f"Main topics discussed: {', '.join(topics)}. "

        # Key themes
        if keywords:
            summary += f"Key themes included: {', '.join(keywords[:5])}. "

        # Activity level
        if len(messages) > 20:
            summary += "This was an active discussion with significant engagement."
        elif len(messages) > 10:
            summary += "The conversation had moderate activity levels."
        else:
            summary += "This was a brief exchange."

        return summary

    @staticmethod
    def _generate_detailed_summary(messages: list[ZulipMessage], context: dict[str, Any]) -> str:
        """Generate a detailed summary (5+ sentences)."""
        participants = context["participants"]
        topics = context["topics"]
        keywords = context["keywords"]
        sentiment = context["sentiment"]

        # Start with overview
        summary = f"Detailed conversation summary: {len(participants)} participants ({', '.join(participants)}) exchanged {len(messages)} messages over {context['time_span_hours']:.1f} hours. "

        # Topics and structure
        if topics:
            summary += f"The discussion covered {len(topics)} main topics: {', '.join(topics)}. "

        # Content analysis
        if keywords:
            summary += f"Key discussion points included: {', '.join(keywords[:8])}. "

        # Sentiment and tone
        sentiment_descriptions = {
            "positive": "The overall tone was positive and collaborative",
            "negative": "The conversation addressed some challenges and concerns",
            "inquisitive": "The discussion was primarily question-driven and exploratory",
            "neutral": "The tone remained neutral and informational"
        }
        summary += sentiment_descriptions.get(sentiment, "The conversation maintained a professional tone") + ". "

        # Message patterns
        if len(messages) > 0:
            first_msg = messages[0]
            last_msg = messages[-1]
            summary += f"The conversation started with {first_msg.sender_full_name} and concluded with {last_msg.sender_full_name}'s input."

        return summary

    @staticmethod
    def _extract_key_points(messages: list[ZulipMessage], context: dict[str, Any]) -> list[str]:
        """Extract key points from the conversation."""
        key_points = []

        # Find messages with questions
        questions = [msg for msg in messages if '?' in msg.content]
        if questions:
            key_points.append(f"Discussion included {len(questions)} questions/inquiries")

        # Find decision-making language
        decision_keywords = ['decide', 'agreed', 'conclusion', 'resolution', 'action', 'next steps']
        decisions = [msg for msg in messages if any(kw in msg.content.lower() for kw in decision_keywords)]
        if decisions:
            key_points.append("Conversation included decision-making or action items")

        # Identify most active participants
        participant_counts = Counter(msg.sender_full_name for msg in messages)
        if participant_counts:
            most_active = participant_counts.most_common(1)[0]
            key_points.append(f"{most_active[0]} was the most active participant ({most_active[1]} messages)")

        # Topic diversity
        topics = context.get("topics", [])
        if len(topics) > 1:
            key_points.append(f"Discussion spanned {len(topics)} different topics")

        return key_points


class SemanticSearchEngine:
    """Enhanced search with semantic understanding."""

    @staticmethod
    def enhance_query(query: str) -> dict[str, Any]:
        """Enhance search query with semantic understanding.
        
        Args:
            query: Original search query
            
        Returns:
            Enhanced query information
        """
        enhanced = {
            "original_query": query,
            "expanded_terms": [],
            "filters": {},
            "search_type": "general"
        }

        query_lower = query.lower()

        # Detect search intent
        if any(word in query_lower for word in ['recent', 'latest', 'today', 'yesterday']):
            enhanced["search_type"] = "temporal"
            enhanced["filters"]["time_relevance"] = True
        elif any(word in query_lower for word in ['error', 'bug', 'issue', 'problem']):
            enhanced["search_type"] = "troubleshooting"
            enhanced["expanded_terms"].extend(['fix', 'solution', 'resolve', 'debug'])
        elif any(word in query_lower for word in ['meeting', 'schedule', 'agenda']):
            enhanced["search_type"] = "planning"
            enhanced["expanded_terms"].extend(['plan', 'organize', 'coordinate'])
        elif any(word in query_lower for word in ['code', 'api', 'function', 'implementation']):
            enhanced["search_type"] = "technical"
            enhanced["expanded_terms"].extend(['develop', 'build', 'create'])

        # Add synonyms and related terms
        term_expansions = {
            'help': ['assistance', 'support', 'aid'],
            'update': ['change', 'modify', 'revision'],
            'complete': ['finish', 'done', 'accomplished'],
            'start': ['begin', 'initiate', 'launch'],
            'review': ['check', 'examine', 'assess']
        }

        for term, synonyms in term_expansions.items():
            if term in query_lower:
                enhanced["expanded_terms"].extend(synonyms)

        return enhanced

    @staticmethod
    async def semantic_search(
        client: AsyncZulipClient,
        query: str,
        stream_name: str | None = None,
        limit: int = 50,
        hours_back: int = 168
    ) -> list[dict[str, Any]]:
        """Perform semantic search across messages.
        
        Args:
            client: Async Zulip client
            query: Search query
            stream_name: Optional stream to search in
            limit: Maximum results to return
            hours_back: How far back to search
            
        Returns:
            List of search results with relevance scores
        """
        # Enhance the query
        enhanced_query = SemanticSearchEngine.enhance_query(query)

        # Get messages based on enhanced query
        search_terms = [enhanced_query["original_query"]] + enhanced_query["expanded_terms"]
        all_results = []

        # Search with different terms
        for term in search_terms[:3]:  # Limit to avoid too many API calls
            try:
                messages = await client.search_messages_async(term, limit=limit//len(search_terms[:3]))
                for msg in messages:
                    # Calculate relevance score
                    score = SemanticSearchEngine._calculate_relevance_score(
                        msg, query, enhanced_query
                    )

                    result = {
                        "message": {
                            "id": msg.id,
                            "sender": msg.sender_full_name,
                            "content": msg.content,
                            "timestamp": msg.timestamp,
                            "stream": msg.stream_name,
                            "topic": msg.subject
                        },
                        "relevance_score": score,
                        "matched_terms": SemanticSearchEngine._find_matched_terms(msg.content, search_terms),
                        "search_type": enhanced_query["search_type"]
                    }
                    all_results.append(result)
            except Exception as e:
                logger.warning(f"Search failed for term '{term}': {e}")
                continue

        # Remove duplicates and sort by relevance
        seen_ids = set()
        unique_results = []
        for result in all_results:
            msg_id = result["message"]["id"]
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                unique_results.append(result)

        # Sort by relevance score (highest first)
        unique_results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return unique_results[:limit]

    @staticmethod
    def _calculate_relevance_score(
        message: ZulipMessage,
        original_query: str,
        enhanced_query: dict[str, Any]
    ) -> float:
        """Calculate relevance score for a message.
        
        Args:
            message: Message to score
            original_query: Original search query
            enhanced_query: Enhanced query information
            
        Returns:
            Relevance score between 0 and 1
        """
        score = 0.0
        content_lower = message.content.lower()
        query_lower = original_query.lower()

        # Exact phrase match (highest weight)
        if query_lower in content_lower:
            score += 0.5

        # Individual term matches
        query_terms = query_lower.split()
        matched_terms = sum(1 for term in query_terms if term in content_lower)
        score += (matched_terms / len(query_terms)) * 0.3

        # Enhanced terms bonus
        expanded_terms = enhanced_query.get("expanded_terms", [])
        enhanced_matches = sum(1 for term in expanded_terms if term in content_lower)
        if expanded_terms:
            score += (enhanced_matches / len(expanded_terms)) * 0.1

        # Recency bonus (newer messages get slight boost)
        now = datetime.now().timestamp()
        age_hours = (now - message.timestamp) / 3600
        if age_hours < 24:
            score += 0.05
        elif age_hours < 168:  # 1 week
            score += 0.02

        # Length penalty for very short messages
        if len(message.content) < 20:
            score *= 0.8

        return min(score, 1.0)  # Cap at 1.0

    @staticmethod
    def _find_matched_terms(content: str, search_terms: list[str]) -> list[str]:
        """Find which search terms matched in the content.
        
        Args:
            content: Message content
            search_terms: List of search terms
            
        Returns:
            List of matched terms
        """
        content_lower = content.lower()
        return [term for term in search_terms if term.lower() in content_lower]


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

        # Analyze conversation context
        context = ConversationAnalyzer.extract_conversation_context(sorted_messages)

        # Generate reply suggestions based on latest message
        latest_message = sorted_messages[-1]  # Most recent message
        suggestions = ConversationAnalyzer.generate_reply_suggestions(context, latest_message)

        return {
            "status": "success",
            "suggestions": suggestions,
            "context": context,
            "latest_message": {
                "sender": latest_message.sender_full_name,
                "content": latest_message.content[:200] + "..." if len(latest_message.content) > 200 else latest_message.content,
                "timestamp": latest_message.timestamp
            }
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

        # Generate summary
        summary_data = ConversationSummarizer.generate_summary(
            messages, summary_type=summary_type
        )

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

        # Perform semantic search
        results = await SemanticSearchEngine.semantic_search(
            client, query, stream_name, limit, hours_back
        )

        if not results:
            # Try fallback with basic search
            try:
                basic_messages = await client.search_messages_async(query, limit)
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
                        "relevance_score": 0.5,
                        "matched_terms": [query],
                        "search_type": "basic_fallback"
                    }
                    for msg in basic_messages
                ]
            except Exception:
                results = []

        # Enhance query for analysis
        enhanced_query = SemanticSearchEngine.enhance_query(query)

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


# Command Chain Integration
class SmartReplyCommand(ProcessDataCommand):
    """Command to generate smart replies as part of a workflow."""

    def __init__(self, stream_name: str, topic: str | None = None, **kwargs):
        """Initialize smart reply command.
        
        Args:
            stream_name: Stream to analyze
            topic: Optional topic filter
        """
        super().__init__(
            name="smart_reply",
            processor=lambda _: asyncio.run(self._async_generate_replies()),
            input_key="dummy",
            output_key="reply_suggestions",
            **kwargs
        )
        self.stream_name = stream_name
        self.topic = topic

    async def _async_generate_replies(self) -> dict[str, Any]:
        """Generate replies asynchronously."""
        result = await smart_reply_impl(self.stream_name, self.topic)
        return result.get("suggestions", [])


class AutoSummarizeCommand(ProcessDataCommand):
    """Command to generate summaries as part of a workflow."""

    def __init__(self, stream_name: str, topic: str | None = None, **kwargs):
        """Initialize auto summarize command.
        
        Args:
            stream_name: Stream to summarize
            topic: Optional topic filter
        """
        super().__init__(
            name="auto_summarize",
            processor=lambda _: asyncio.run(self._async_generate_summary()),
            input_key="dummy",
            output_key="conversation_summary",
            **kwargs
        )
        self.stream_name = stream_name
        self.topic = topic

    async def _async_generate_summary(self) -> dict[str, Any]:
        """Generate summary asynchronously."""
        result = await auto_summarize_impl(self.stream_name, self.topic)
        return result


def create_smart_workflow_chain(
    stream_name: str,
    topic: str | None = None,
    include_search: bool = False,
    search_query: str | None = None
) -> CommandChain:
    """Create a workflow chain with intelligent assistant tools.
    
    Args:
        stream_name: Stream to analyze
        topic: Optional topic filter
        include_search: Whether to include smart search
        search_query: Query for smart search if included
        
    Returns:
        Configured command chain with assistant tools
    """
    chain = CommandChain("smart_assistant_workflow")

    # Add summary generation
    chain.add_command(AutoSummarizeCommand(stream_name, topic))

    # Add reply suggestions
    chain.add_command(SmartReplyCommand(stream_name, topic))

    # Optionally add smart search
    if include_search and search_query:
        chain.add_command(ProcessDataCommand(
            name="smart_search",
            processor=lambda _: asyncio.run(smart_search_impl(search_query, stream_name)),
            input_key="dummy",
            output_key="search_results"
        ))

    return chain
