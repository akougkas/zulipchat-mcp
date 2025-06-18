"""MCP server for Zulip integration."""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource

from .client import ZulipClientWrapper
from .config import ConfigManager


# Initialize FastMCP server
mcp = FastMCP("ZulipChat MCP")

# Global client instance
zulip_client: Optional[ZulipClientWrapper] = None
config_manager: Optional[ConfigManager] = None


def get_client() -> ZulipClientWrapper:
    """Get or create Zulip client instance."""
    global zulip_client, config_manager
    if zulip_client is None:
        config_manager = ConfigManager()
        zulip_client = ZulipClientWrapper(config_manager)
    return zulip_client


@mcp.tool()
def send_message(
    message_type: str,
    to: str,
    content: str,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """Send a message to a Zulip stream or user.
    
    Args:
        message_type: Type of message ("stream" or "private")
        to: Stream name or user email/username
        content: Message content
        topic: Topic name (required for stream messages)
    """
    client = get_client()
    
    if message_type == "stream" and not topic:
        return {"error": "Topic is required for stream messages"}
    
    # Convert to list for private messages if needed
    recipients = [to] if message_type == "private" else to
    
    result = client.send_message(message_type, recipients, content, topic)
    return result


@mcp.tool()
def get_messages(
    stream_name: Optional[str] = None,
    topic: Optional[str] = None,
    hours_back: int = 24,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get messages from Zulip.
    
    Args:
        stream_name: Stream to get messages from (optional)
        topic: Topic to filter by (optional)
        hours_back: How many hours back to search
        limit: Maximum number of messages to return
    """
    client = get_client()
    
    if stream_name:
        messages = client.get_messages_from_stream(stream_name, topic, hours_back)
    else:
        messages = client.get_messages(num_before=limit)
    
    # Convert to dict format for JSON serialization
    return [
        {
            "id": msg.id,
            "sender": msg.sender_full_name,
            "sender_email": msg.sender_email,
            "timestamp": msg.timestamp,
            "content": msg.content,
            "stream": msg.stream_name,
            "topic": msg.subject,
            "type": msg.type,
            "reactions": msg.reactions
        }
        for msg in messages[:limit]
    ]


@mcp.tool()
def search_messages(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search messages by content.
    
    Args:
        query: Search query
        limit: Maximum number of results
    """
    client = get_client()
    messages = client.search_messages(query, limit)
    
    return [
        {
            "id": msg.id,
            "sender": msg.sender_full_name,
            "timestamp": msg.timestamp,
            "content": msg.content,
            "stream": msg.stream_name,
            "topic": msg.subject,
            "relevance_score": 1.0  # Zulip doesn't provide relevance scores
        }
        for msg in messages
    ]


@mcp.tool()
def get_streams() -> List[Dict[str, Any]]:
    """Get list of available streams."""
    client = get_client()
    streams = client.get_streams()
    
    return [
        {
            "id": stream.stream_id,
            "name": stream.name,
            "description": stream.description,
            "is_private": stream.is_private
        }
        for stream in streams
    ]


@mcp.tool()
def get_users() -> List[Dict[str, Any]]:
    """Get list of users in the organization."""
    client = get_client()
    users = client.get_users()
    
    return [
        {
            "id": user.user_id,
            "name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
            "is_bot": user.is_bot,
            "avatar_url": user.avatar_url
        }
        for user in users
    ]


@mcp.tool()
def add_reaction(message_id: int, emoji_name: str) -> Dict[str, Any]:
    """Add a reaction to a message.
    
    Args:
        message_id: ID of the message to react to
        emoji_name: Name of the emoji (e.g., "thumbs_up", "heart")
    """
    client = get_client()
    return client.add_reaction(message_id, emoji_name)


@mcp.tool()
def edit_message(
    message_id: int,
    content: Optional[str] = None,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """Edit a message.
    
    Args:
        message_id: ID of the message to edit
        content: New content (optional)
        topic: New topic (optional)
    """
    client = get_client()
    return client.edit_message(message_id, content, topic)


@mcp.tool()
def get_daily_summary(
    streams: Optional[List[str]] = None,
    hours_back: int = 24
) -> Dict[str, Any]:
    """Get a summary of daily activity.
    
    Args:
        streams: List of stream names to include (optional)
        hours_back: Hours to look back for the summary
    """
    client = get_client()
    return client.get_daily_summary(streams, hours_back)


# Resource definitions
@mcp.resource("messages://{stream_name}")
def get_stream_messages(stream_name: str) -> str:
    """Get recent messages from a specific stream."""
    client = get_client()
    messages = client.get_messages_from_stream(stream_name, hours_back=24)
    
    content = f"# Messages from #{stream_name} (Last 24 hours)\n\n"
    
    for msg in messages:
        timestamp = datetime.fromtimestamp(msg.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        content += f"**{msg.sender_full_name}** ({timestamp})\n"
        if msg.subject:
            content += f"*Topic: {msg.subject}*\n"
        content += f"{msg.content}\n\n---\n\n"
    
    return content


@mcp.resource("streams://all")
def get_all_streams() -> str:
    """Get information about all available streams."""
    client = get_client()
    streams = client.get_streams()
    
    content = "# Available Zulip Streams\n\n"
    
    for stream in streams:
        privacy = "🔒 Private" if stream.is_private else "🌐 Public"
        content += f"## {stream.name} ({privacy})\n"
        content += f"**ID:** {stream.stream_id}\n"
        content += f"**Description:** {stream.description}\n\n"
    
    return content


@mcp.resource("users://all")
def get_all_users() -> str:
    """Get information about all users."""
    client = get_client()
    users = client.get_users()
    
    content = "# Organization Users\n\n"
    
    active_users = [u for u in users if u.is_active and not u.is_bot]
    bots = [u for u in users if u.is_bot]
    
    content += f"## Active Users ({len(active_users)})\n\n"
    for user in active_users:
        content += f"- **{user.full_name}** ({user.email})\n"
    
    content += f"\n## Bots ({len(bots)})\n\n"
    for bot in bots:
        content += f"- **{bot.full_name}** ({bot.email})\n"
    
    return content


# Custom prompts for team communication workflows
@mcp.prompt("summarize")
def summarize_day(
    streams: Optional[List[str]] = None,
    hours_back: int = 24
) -> List[Any]:
    """Generate an end-of-day summary with message stats and key conversations.
    
    Args:
        streams: List of stream names to include in summary
        hours_back: Number of hours to look back
    """
    client = get_client()
    summary = client.get_daily_summary(streams, hours_back)
    
    content = f"# Daily Summary - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    content += f"**Time Range:** {summary['time_range']}\n"
    content += f"**Total Messages:** {summary['total_messages']}\n\n"
    
    # Stream activity
    content += "## Stream Activity\n\n"
    for stream_name, stream_data in summary['streams'].items():
        content += f"### #{stream_name}\n"
        content += f"- **Messages:** {stream_data['message_count']}\n"
        
        if stream_data['topics']:
            content += "- **Active Topics:**\n"
            for topic, count in list(stream_data['topics'].items())[:5]:
                content += f"  - {topic}: {count} messages\n"
        content += "\n"
    
    # Top contributors
    if summary['top_senders']:
        content += "## Top Contributors\n\n"
        for sender, count in list(summary['top_senders'].items())[:5]:
            content += f"- **{sender}:** {count} messages\n"
    
    return [TextContent(type="text", text=content)]


@mcp.prompt("prepare")
def prepare_morning_briefing(
    streams: Optional[List[str]] = None,
    days_back: int = 7
) -> List[Any]:
    """Generate a morning briefing with yesterday's highlights and weekly overview.
    
    Args:
        streams: List of stream names to include
        days_back: Number of days to look back for weekly overview
    """
    client = get_client()
    
    # Yesterday's summary
    yesterday_summary = client.get_daily_summary(streams, 24)
    
    # Weekly overview
    weekly_summary = client.get_daily_summary(streams, days_back * 24)
    
    content = f"# Morning Briefing - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    
    # Yesterday's highlights
    content += "## Yesterday's Highlights\n\n"
    content += f"**Total Messages:** {yesterday_summary['total_messages']}\n\n"
    
    if yesterday_summary['streams']:
        content += "### Most Active Streams:\n"
        sorted_streams = sorted(
            yesterday_summary['streams'].items(),
            key=lambda x: x[1]['message_count'],
            reverse=True
        )
        
        for stream_name, stream_data in sorted_streams[:3]:
            content += f"- **#{stream_name}:** {stream_data['message_count']} messages\n"
            
            # Show top topics
            if stream_data['topics']:
                top_topics = sorted(
                    stream_data['topics'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:2]
                for topic, count in top_topics:
                    content += f"  - {topic} ({count} messages)\n"
    
    # Weekly overview
    content += f"\n## Weekly Overview (Last {days_back} days)\n\n"
    content += f"**Total Messages:** {weekly_summary['total_messages']}\n"
    content += f"**Average Daily Messages:** {weekly_summary['total_messages'] // days_back}\n\n"
    
    if weekly_summary['top_senders']:
        content += "### Most Active Contributors:\n"
        for sender, count in list(weekly_summary['top_senders'].items())[:5]:
            content += f"- **{sender}:** {count} messages\n"
    
    return [TextContent(type="text", text=content)]


@mcp.prompt("catch_up")
def catch_up_summary(
    streams: Optional[List[str]] = None,
    hours_back: int = 8
) -> List[Any]:
    """Generate a quick catch-up summary for missed messages.
    
    Args:
        streams: List of stream names to include
        hours_back: Number of hours to look back
    """
    client = get_client()
    
    content = f"# Catch-Up Summary\n\n"
    content += f"**Missed Messages from Last {hours_back} Hours**\n\n"
    
    if streams:
        target_streams = streams
    else:
        # Get all subscribed streams
        all_streams = client.get_streams()
        target_streams = [s.name for s in all_streams if not s.is_private][:10]  # Limit to 10
    
    total_messages = 0
    
    for stream_name in target_streams:
        messages = client.get_messages_from_stream(stream_name, hours_back=hours_back)
        if messages:
            total_messages += len(messages)
            content += f"## #{stream_name} ({len(messages)} messages)\n\n"
            
            # Group by topic
            topics = {}
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


def main():
    """Main entry point for the MCP server."""
    if len(sys.argv) < 2:
        print("Usage: zulipchat-mcp <command>")
        print("Commands: server")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "server":
        # Test configuration
        try:
            config_manager = ConfigManager()
            if not config_manager.validate_config():
                print("❌ Invalid configuration. Please check your settings.")
                sys.exit(1)
            
            # Test client connection
            client = get_client()
            streams = client.get_streams()
            print(f"✅ Connected to Zulip! Found {len(streams)} streams.")
        except Exception as e:
            print(f"❌ Failed to connect to Zulip: {e}")
            print("\nPlease check your configuration:")
            print("- ZULIP_EMAIL environment variable")
            print("- ZULIP_API_KEY environment variable") 
            print("- ZULIP_SITE environment variable")
            print("- Or configuration file at ~/.config/zulipchat-mcp/config.json")
            sys.exit(1)
        
        # Start the MCP server
        mcp.run()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()