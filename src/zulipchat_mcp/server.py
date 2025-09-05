"""Enhanced MCP server for Zulip integration with security and error handling."""

import html
import logging
import re
import sys
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

# Import assistant tools to register them with FastMCP

# Set up logging
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("ZulipChat MCP")

# Global client instance
zulip_client = None
config_manager = None


# Inline security functions (to avoid import issues)
def sanitize_input(content: str, max_length: int = 10000) -> str:
    """Sanitize user input to prevent injection attacks."""
    content = html.escape(content)
    content = re.sub(r'`', '', content)
    return content[:max_length]


def validate_stream_name(name: str) -> bool:
    """Validate stream name against injection."""
    pattern = r'^[a-zA-Z0-9\-_\s\.]+$'
    return bool(re.match(pattern, name)) and 0 < len(name) <= 100


def validate_topic(topic: str) -> bool:
    """Validate topic name against injection."""
    pattern = r'^[a-zA-Z0-9\-_\s\.\,\!\?\(\)]+$'
    return bool(re.match(pattern, topic)) and 0 < len(topic) <= 200


def validate_message_type(message_type: str) -> bool:
    """Validate message type."""
    return message_type in ["stream", "private"]


def validate_emoji(emoji_name: str) -> bool:
    """Validate emoji name."""
    pattern = r'^[a-zA-Z0-9_]+$'
    return bool(re.match(pattern, emoji_name)) and 0 < len(emoji_name) <= 50


def get_client():
    """Get or create Zulip client instance."""
    global zulip_client, config_manager
    if zulip_client is None:
        from .client import ZulipClientWrapper
        from .config import ConfigManager
        config_manager = ConfigManager()
        zulip_client = ZulipClientWrapper(config_manager)
    return zulip_client


@mcp.tool()
def send_message(
    message_type: str, to: str, content: str, topic: str | None = None
) -> dict[str, Any]:
    """Send a message to a Zulip stream or user with enhanced security.

    Args:
        message_type: Type of message ("stream" or "private")
        to: Stream name or user email/username
        content: Message content
        topic: Topic name (required for stream messages)
    """
    try:
        # Validate inputs
        if not validate_message_type(message_type):
            return {"status": "error", "error": f"Invalid message_type: {message_type}"}

        if message_type == "stream":
            if not topic:
                return {"status": "error", "error": "Topic required for stream messages"}
            if not validate_stream_name(to):
                return {"status": "error", "error": f"Invalid stream name: {to}"}
            if not validate_topic(topic):
                return {"status": "error", "error": f"Invalid topic: {topic}"}

        # Sanitize content
        content = sanitize_input(content)

        # Get client and send message
        client = get_client()
        recipients = [to] if message_type == "private" else to
        result = client.send_message(message_type, recipients, content, topic)

        # Add metadata to response
        if result.get("result") == "success":
            return {
                "status": "success",
                "message_id": result.get("id"),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"status": "error", "error": result.get("msg", "Unknown error")}

    except ValueError as e:
        logger.error(f"Validation error in send_message: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}")
        return {"status": "error", "error": "Internal server error"}


@mcp.tool()
def get_messages(
    stream_name: str | None = None,
    topic: str | None = None,
    hours_back: int = 24,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get messages from Zulip with enhanced validation.

    Args:
        stream_name: Stream to get messages from (optional)
        topic: Topic to filter by (optional)
        hours_back: How many hours back to retrieve messages
        limit: Maximum number of messages to return
    """
    try:
        # Validate inputs
        if stream_name and not validate_stream_name(stream_name):
            return [{"error": f"Invalid stream name: {stream_name}"}]
        if topic and not validate_topic(topic):
            return [{"error": f"Invalid topic: {topic}"}]
        if not 1 <= hours_back <= 168:  # Max 1 week
            return [{"error": "hours_back must be between 1 and 168"}]
        if not 1 <= limit <= 100:
            return [{"error": "limit must be between 1 and 100"}]

        client = get_client()

        if stream_name:
            messages = client.get_messages_from_stream(
                stream_name, topic=topic, hours_back=hours_back
            )[:limit]
        else:
            messages = client.get_messages(num_before=limit)

        return [
            {
                "id": msg.id,
                "sender": msg.sender_full_name,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "stream": msg.stream_name,
                "topic": msg.subject,
            }
            for msg in messages
        ]
    except Exception as e:
        logger.error(f"Error in get_messages: {e}")
        return [{"error": "Failed to retrieve messages"}]


@mcp.tool()
def search_messages(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Search messages by content with sanitization.

    Args:
        query: Search query
        limit: Maximum number of results
    """
    try:
        # Sanitize and validate query
        query = sanitize_input(query, max_length=200)
        if not query:
            return [{"error": "Query cannot be empty"}]
        if not 1 <= limit <= 100:
            return [{"error": "limit must be between 1 and 100"}]

        client = get_client()
        messages = client.search_messages(query, num_results=limit)

        return [
            {
                "id": msg.id,
                "sender": msg.sender_full_name,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "stream": msg.stream_name,
                "topic": msg.subject,
            }
            for msg in messages
        ]
    except Exception as e:
        logger.error(f"Error in search_messages: {e}")
        return [{"error": "Search failed"}]


@mcp.tool()
def get_streams() -> list[dict[str, Any]]:
    """Get list of available streams."""
    try:
        client = get_client()
        streams = client.get_streams()

        return [
            {
                "id": stream.stream_id,
                "name": stream.name,
                "description": stream.description,
                "is_private": stream.is_private,
            }
            for stream in streams
        ]
    except Exception as e:
        logger.error(f"Error in get_streams: {e}")
        return [{"error": "Failed to retrieve streams"}]


@mcp.tool()
def get_users() -> list[dict[str, Any]]:
    """Get list of users."""
    try:
        client = get_client()
        users = client.get_users()

        return [
            {
                "id": user.user_id,
                "name": user.full_name,
                "email": user.email,
                "is_active": user.is_active,
                "is_bot": user.is_bot,
            }
            for user in users
        ]
    except Exception as e:
        logger.error(f"Error in get_users: {e}")
        return [{"error": "Failed to retrieve users"}]


@mcp.tool()
def add_reaction(message_id: int, emoji_name: str) -> dict[str, Any]:
    """Add a reaction to a message with validation.

    Args:
        message_id: ID of the message to react to
        emoji_name: Name of the emoji reaction
    """
    try:
        # Validate inputs
        if not isinstance(message_id, int) or message_id <= 0:
            return {"status": "error", "error": "Invalid message ID"}
        if not validate_emoji(emoji_name):
            return {"status": "error", "error": f"Invalid emoji name: {emoji_name}"}

        client = get_client()
        result = client.add_reaction(message_id, emoji_name)

        if result.get("result") == "success":
            return {"status": "success", "message": "Reaction added"}
        else:
            return {"status": "error", "error": result.get("msg", "Unknown error")}

    except Exception as e:
        logger.error(f"Error in add_reaction: {e}")
        return {"status": "error", "error": "Failed to add reaction"}


@mcp.tool()
def edit_message(
    message_id: int, content: str | None = None, topic: str | None = None
) -> dict[str, Any]:
    """Edit a message with validation.

    Args:
        message_id: ID of the message to edit
        content: New content (optional)
        topic: New topic (optional)
    """
    try:
        # Validate inputs
        if not isinstance(message_id, int) or message_id <= 0:
            return {"status": "error", "error": "Invalid message ID"}
        if content:
            content = sanitize_input(content)
        if topic and not validate_topic(topic):
            return {"status": "error", "error": f"Invalid topic: {topic}"}
        if not content and not topic:
            return {"status": "error", "error": "Must provide content or topic to edit"}

        client = get_client()
        result = client.edit_message(message_id, content, topic)

        if result.get("result") == "success":
            return {"status": "success", "message": "Message edited"}
        else:
            return {"status": "error", "error": result.get("msg", "Unknown error")}

    except Exception as e:
        logger.error(f"Error in edit_message: {e}")
        return {"status": "error", "error": "Failed to edit message"}


@mcp.tool()
def get_daily_summary(
    streams: list[str] | None = None, hours_back: int = 24
) -> dict[str, Any]:
    """Get a summary of daily activity with validation.

    Args:
        streams: List of stream names to include (optional)
        hours_back: Number of hours to look back
    """
    try:
        # Validate inputs
        if streams:
            for stream in streams:
                if not validate_stream_name(stream):
                    return {"status": "error", "error": f"Invalid stream name: {stream}"}
        if not 1 <= hours_back <= 168:  # Max 1 week
            return {"status": "error", "error": "hours_back must be between 1 and 168"}

        client = get_client()
        summary = client.get_daily_summary(streams, hours_back)
        return {"status": "success", "data": summary}

    except Exception as e:
        logger.error(f"Error in get_daily_summary: {e}")
        return {"status": "error", "error": "Failed to generate summary"}


# Resources
@mcp.resource("messages://stream/{stream_name}")
def get_stream_messages(stream_name: str) -> list[TextContent]:
    """Get recent messages from a stream as a resource."""
    try:
        if not validate_stream_name(stream_name):
            return [TextContent(type="text", text=f"Invalid stream name: {stream_name}")]

        client = get_client()
        messages = client.get_messages_from_stream(stream_name)

        content = f"# Messages from #{stream_name}\n\n"
        for msg in messages[:50]:
            timestamp = datetime.fromtimestamp(msg.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            content += f"## {msg.subject or 'No topic'}\n"
            content += f"**{msg.sender_full_name}** at {timestamp}:\n"
            content += f"{msg.content}\n\n"

        return [TextContent(type="text", text=content)]
    except Exception as e:
        logger.error(f"Error in get_stream_messages resource: {e}")
        return [TextContent(type="text", text="Failed to retrieve messages")]


@mcp.resource("streams://list")
def list_streams() -> list[TextContent]:
    """List all available streams as a resource."""
    try:
        client = get_client()
        streams = client.get_streams()

        content = "# Available Zulip Streams\n\n"
        for stream in streams:
            status = "🔒 Private" if stream.is_private else "📢 Public"
            content += f"- **{stream.name}** ({status}): {stream.description}\n"

        return [TextContent(type="text", text=content)]
    except Exception as e:
        logger.error(f"Error in list_streams resource: {e}")
        return [TextContent(type="text", text="Failed to retrieve streams")]


@mcp.resource("users://list")
def list_users() -> list[TextContent]:
    """List all users as a resource."""
    try:
        client = get_client()
        users = client.get_users()

        content = "# Zulip Users\n\n"
        active_users = [u for u in users if u.is_active and not u.is_bot]
        bots = [u for u in users if u.is_bot]

        content += f"## Active Users ({len(active_users)})\n\n"
        for user in active_users:
            content += f"- **{user.full_name}** ({user.email})\n"

        if bots:
            content += f"\n## Bots ({len(bots)})\n\n"
            for bot in bots:
                content += f"- **{bot.full_name}** ({bot.email})\n"

        return [TextContent(type="text", text=content)]
    except Exception as e:
        logger.error(f"Error in list_users resource: {e}")
        return [TextContent(type="text", text="Failed to retrieve users")]


# Prompts
@mcp.prompt()
def daily_summary_prompt(
    streams: list[str] | None = None, hours: int = 24
) -> list[Any]:
    """Generate an end-of-day summary with message stats and key conversations.

    Args:
        streams: List of stream names to include in summary
        hours: Number of hours to look back (default: 24)
    """
    try:
        if streams:
            for stream in streams:
                if not validate_stream_name(stream):
                    return [TextContent(type="text", text=f"Invalid stream name: {stream}")]
        if not 1 <= hours <= 168:
            return [TextContent(type="text", text="hours must be between 1 and 168")]

        client = get_client()

        # Get all streams if none specified
        if not streams:
            all_streams = client.get_streams()
            streams = [s.name for s in all_streams if not s.is_private][:10]

        summary = client.get_daily_summary(streams, hours)

        content = "# Zulip Daily Summary\n\n"
        content += f"**Period**: Last {hours} hours\n"
        content += f"**Total Messages**: {summary['total_messages']}\n\n"

        if summary["streams"]:
            content += "## Stream Activity\n\n"
            for stream_name, stream_data in summary["streams"].items():
                content += f"### #{stream_name}\n"
                content += f"- Messages: {stream_data['message_count']}\n"
                if stream_data["topics"]:
                    content += "- Top topics:\n"
                    for topic, count in list(stream_data["topics"].items())[:5]:
                        content += f"  - {topic}: {count} messages\n"
                content += "\n"

        if summary["top_senders"]:
            content += "## Most Active Users\n\n"
            for sender, count in list(summary["top_senders"].items())[:10]:
                content += f"- {sender}: {count} messages\n"

        return [TextContent(type="text", text=content)]
    except Exception as e:
        logger.error(f"Error in daily_summary_prompt: {e}")
        return [TextContent(type="text", text="Failed to generate summary")]


@mcp.prompt()
def morning_briefing_prompt(
    streams: list[str] | None = None,
) -> list[Any]:
    """Generate a morning briefing with yesterday's highlights and weekly overview.

    Args:
        streams: List of stream names to include
    """
    try:
        if streams:
            for stream in streams:
                if not validate_stream_name(stream):
                    return [TextContent(type="text", text=f"Invalid stream name: {stream}")]

        client = get_client()

        # Get summaries for different periods
        yesterday = client.get_daily_summary(streams, 24)
        week = client.get_daily_summary(streams, 168)

        content = "# Good Morning! Here's your Zulip briefing\n\n"

        # Yesterday's highlights
        content += "## Yesterday's Activity\n"
        content += f"- Total messages: {yesterday['total_messages']}\n"
        content += f"- Active streams: {len(yesterday['streams'])}\n"

        if yesterday["top_senders"]:
            top_sender = list(yesterday["top_senders"].items())[0]
            content += f"- Most active: {top_sender[0]} ({top_sender[1]} messages)\n"

        # Weekly overview
        content += "\n## This Week\n"
        content += f"- Total messages: {week['total_messages']}\n"
        avg_daily = week["total_messages"] // 7
        content += f"- Daily average: {avg_daily} messages\n"

        # Most active streams this week
        if week["streams"]:
            content += "\n### Most Active Streams\n"
            sorted_streams = sorted(
                week["streams"].items(), key=lambda x: x[1]["message_count"], reverse=True
            )[:5]
            for stream_name, stream_data in sorted_streams:
                content += f"- #{stream_name}: {stream_data['message_count']} messages\n"

        # Trending topics
        all_topics = {}
        for stream_data in week["streams"].values():
            for topic, count in stream_data["topics"].items():
                all_topics[topic] = all_topics.get(topic, 0) + count

        if all_topics:
            content += "\n### Trending Topics\n"
            sorted_topics = sorted(all_topics.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]
            for topic, count in sorted_topics:
                content += f"- {topic}: {count} messages\n"

        return [TextContent(type="text", text=content)]
    except Exception as e:
        logger.error(f"Error in morning_briefing_prompt: {e}")
        return [TextContent(type="text", text="Failed to generate briefing")]


@mcp.prompt()
def catch_up_prompt(
    streams: list[str] | None = None, hours: int = 4
) -> list[Any]:
    """Generate a quick catch-up summary for missed messages.

    Args:
        streams: List of stream names to include
        hours: Number of hours to catch up on (default: 4)
    """
    try:
        if streams:
            for stream in streams:
                if not validate_stream_name(stream):
                    return [TextContent(type="text", text=f"Invalid stream name: {stream}")]
        if not 1 <= hours <= 24:
            return [TextContent(type="text", text="hours must be between 1 and 24")]

        client = get_client()

        # Get streams if not specified
        target_streams = streams
        if not target_streams:
            all_streams = client.get_streams()
            target_streams = [s.name for s in all_streams if not s.is_private][:5]

        content = f"# Quick Catch-Up (Last {hours} hours)\n\n"
        total_messages = 0

        for stream_name in target_streams:
            messages = client.get_messages_from_stream(stream_name, hours_back=hours)
            if messages:
                total_messages += len(messages)
                content += f"## #{stream_name} ({len(messages)} messages)\n\n"

                # Group by topic
                topics: dict[str, list[Any]] = {}
                for msg in messages:
                    topic = msg.subject or "General"
                    if topic not in topics:
                        topics[topic] = []
                    topics[topic].append(msg)

                for topic, topic_messages in topics.items():
                    content += f"### {topic}\n"
                    # Show latest 3 messages per topic
                    for msg in topic_messages[-3:]:
                        timestamp = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")
                        content += f"- **{msg.sender_full_name}** ({timestamp}): {msg.content[:100]}...\n"
                    content += "\n"

        if total_messages == 0:
            content += "No new messages in the selected streams.\n"
        else:
            content += f"\n**Total: {total_messages} messages across {len(target_streams)} streams**\n"

        return [TextContent(type="text", text=content)]
    except Exception as e:
        logger.error(f"Error in catch_up_prompt: {e}")
        return [TextContent(type="text", text="Failed to generate catch-up")]


# Import and register assistant tools
from .assistants import auto_summarize_impl, smart_reply_impl, smart_search_impl


@mcp.tool()
async def smart_reply(
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
    return await smart_reply_impl(stream_name, topic, hours_back, context_messages)


@mcp.tool()
async def auto_summarize(
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
    return await auto_summarize_impl(stream_name, topic, hours_back, summary_type, max_messages)


@mcp.tool()
async def smart_search(
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
    return await smart_search_impl(query, stream_name, hours_back, limit)


def main() -> None:
    """Main entry point for the MCP server."""
    if len(sys.argv) < 2:
        print("Usage: zulipchat-mcp <command>")
        print("Commands: server")
        sys.exit(1)

    command = sys.argv[1]
    if command == "server":
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Start the MCP server
        mcp.run()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
