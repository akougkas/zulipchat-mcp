#!/usr/bin/env python3
"""
ZulipChat MCP Slash Commands

This module provides slash command implementations that can be used by various AI agents
(Claude Code, Cursor, Cascade, etc.) to interact with the ZulipChat MCP server.

The slash commands wrap the MCP prompts for easy access:
- /zulipchat:summarize - Daily summary with message stats
- /zulipchat:prepare - Morning briefing with highlights  
- /zulipchat:catch_up - Quick catch-up for missed messages
"""

import sys
import os
from typing import Optional, List
from datetime import datetime

# Add the src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from zulipchat_mcp.client import ZulipClientWrapper
    from zulipchat_mcp.config import ConfigManager
except ImportError as e:
    print(f"Error: Could not import ZulipChat MCP modules: {e}")
    print("Make sure you're running this from the zulipchat-mcp directory and dependencies are installed.")
    sys.exit(1)


def get_mcp_client() -> ZulipClientWrapper:
    """Get or create a ZulipChat MCP client instance."""
    try:
        config_manager = ConfigManager()
        return ZulipClientWrapper(config_manager)
    except Exception as e:
        print(f"Error initializing ZulipChat MCP client: {e}")
        print("Please check your Zulip configuration (ZULIP_EMAIL, ZULIP_API_KEY, ZULIP_SITE)")
        sys.exit(1)


def parse_arguments(args_string: str) -> tuple[Optional[List[str]], Optional[int]]:
    """Parse slash command arguments into streams and time parameter."""
    if not args_string.strip():
        return None, None
    
    parts = args_string.strip().split()
    streams = None
    time_param = None
    
    if len(parts) >= 1:
        # First part could be streams (comma-separated)
        if ',' in parts[0] or not parts[0].isdigit():
            streams = [s.strip() for s in parts[0].split(',')]
    
    if len(parts) >= 2:
        # Second part should be numeric (hours or days)
        try:
            time_param = int(parts[1])
        except ValueError:
            print(f"Warning: Invalid time parameter '{parts[1]}', using default")
    elif len(parts) == 1 and parts[0].isdigit():
        # Single numeric argument
        time_param = int(parts[0])
        streams = None
    
    return streams, time_param


def zulipchat_summarize(arguments: str = "") -> str:
    """
    /zulipchat:summarize - Generate daily summary with message stats and key conversations
    
    Usage:
        /zulipchat:summarize
        /zulipchat:summarize general,development 48
    
    Args:
        arguments: Optional "streams hours_back" (e.g., "general,dev 24")
    """
    client = get_mcp_client()
    streams, hours_back = parse_arguments(arguments)
    hours_back = hours_back or 24
    
    print(f"🔍 Generating daily summary (last {hours_back} hours)...")
    if streams:
        print(f"📊 Focusing on streams: {', '.join(streams)}")
    
    try:
        summary = client.get_daily_summary(streams, hours_back)
        
        content = f"# 📈 Daily Summary - {datetime.now().strftime('%Y-%m-%d')}\n\n"
        content += f"**⏱️ Time Range:** {summary['time_range']}\n"
        content += f"**💬 Total Messages:** {summary['total_messages']}\n\n"
        
        if summary['total_messages'] == 0:
            content += "🔇 No messages found in the specified time range.\n"
            return content
        
        # Stream activity
        content += "## 🏞️ Stream Activity\n\n"
        sorted_streams = sorted(
            summary['streams'].items(),
            key=lambda x: x[1]['message_count'],
            reverse=True
        )
        
        for stream_name, stream_data in sorted_streams:
            if stream_data['message_count'] > 0:
                content += f"### #{stream_name}\n"
                content += f"- **Messages:** {stream_data['message_count']}\n"
                
                if stream_data['topics']:
                    content += "- **Active Topics:**\n"
                    for topic, count in list(stream_data['topics'].items())[:5]:
                        content += f"  - {topic}: {count} messages\n"
                content += "\n"
        
        # Top contributors
        if summary['top_senders']:
            content += "## 👥 Top Contributors\n\n"
            for sender, count in list(summary['top_senders'].items())[:5]:
                content += f"- **{sender}:** {count} messages\n"
        
        return content
        
    except Exception as e:
        return f"❌ Error generating summary: {e}"


def zulipchat_prepare(arguments: str = "") -> str:
    """
    /zulipchat:prepare - Generate morning briefing with yesterday's highlights and weekly overview
    
    Usage:
        /zulipchat:prepare
        /zulipchat:prepare general,team-updates 5
    
    Args:
        arguments: Optional "streams days_back" (e.g., "general,dev 7")
    """
    client = get_mcp_client()
    streams, days_back = parse_arguments(arguments)
    days_back = days_back or 7
    
    print(f"🌅 Generating morning briefing...")
    if streams:
        print(f"📊 Focusing on streams: {', '.join(streams)}")
    print(f"📅 Weekly overview: last {days_back} days")
    
    try:
        # Yesterday's summary
        yesterday_summary = client.get_daily_summary(streams, 24)
        
        # Weekly overview  
        weekly_summary = client.get_daily_summary(streams, days_back * 24)
        
        content = f"# 🌅 Morning Briefing - {datetime.now().strftime('%Y-%m-%d')}\n\n"
        
        # Yesterday's highlights
        content += "## 📊 Yesterday's Highlights\n\n"
        content += f"**💬 Total Messages:** {yesterday_summary['total_messages']}\n\n"
        
        if yesterday_summary['streams']:
            content += "### 🔥 Most Active Streams:\n"
            sorted_streams = sorted(
                yesterday_summary['streams'].items(),
                key=lambda x: x[1]['message_count'],
                reverse=True
            )
            
            for stream_name, stream_data in sorted_streams[:3]:
                if stream_data['message_count'] > 0:
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
        content += f"\n## 📈 Weekly Overview (Last {days_back} days)\n\n"
        content += f"**💬 Total Messages:** {weekly_summary['total_messages']}\n"
        if days_back > 0:
            avg_daily = weekly_summary['total_messages'] // days_back
            content += f"**📊 Average Daily Messages:** {avg_daily}\n\n"
        
        if weekly_summary['top_senders']:
            content += "### 👥 Most Active Contributors:\n"
            for sender, count in list(weekly_summary['top_senders'].items())[:5]:
                content += f"- **{sender}:** {count} messages\n"
        
        return content
        
    except Exception as e:
        return f"❌ Error generating morning briefing: {e}"


def zulipchat_catch_up(arguments: str = "") -> str:
    """
    /zulipchat:catch_up - Generate quick catch-up summary for missed messages
    
    Usage:
        /zulipchat:catch_up
        /zulipchat:catch_up general,development 4
    
    Args:
        arguments: Optional "streams hours_back" (e.g., "general,dev 8")
    """
    client = get_mcp_client()
    streams, hours_back = parse_arguments(arguments)
    hours_back = hours_back or 8
    
    print(f"⚡ Generating catch-up summary (last {hours_back} hours)...")
    if streams:
        print(f"📊 Focusing on streams: {', '.join(streams)}")
    
    try:
        content = f"# ⚡ Catch-Up Summary\n\n"
        content += f"**📅 Missed Messages from Last {hours_back} Hours**\n\n"
        
        if streams:
            target_streams = streams
        else:
            # Get all public streams, limit to reasonable number
            all_streams = client.get_streams()
            target_streams = [s.name for s in all_streams if not s.is_private][:10]
        
        total_messages = 0
        
        for stream_name in target_streams:
            try:
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
                        content += f"### 💬 {topic}\n"
                        content += f"- **{len(topic_messages)} messages** from "
                        senders = list(set(msg.sender_full_name for msg in topic_messages))
                        content += f"{', '.join(senders[:3])}"
                        if len(senders) > 3:
                            content += f" and {len(senders) - 3} others"
                        content += "\n\n"
                        
                        # Show latest message preview
                        latest_msg = max(topic_messages, key=lambda m: m.timestamp)
                        preview = latest_msg.content[:100] + "..." if len(latest_msg.content) > 100 else latest_msg.content
                        content += f"*Latest: {preview}*\n\n"
            
            except Exception as stream_error:
                print(f"Warning: Could not fetch messages from #{stream_name}: {stream_error}")
                continue
        
        if total_messages == 0:
            content += "🔇 No new messages found in the specified streams and time range.\n"
        else:
            content += f"---\n**📊 Total: {total_messages} messages across {len(target_streams)} streams**\n"
        
        return content
        
    except Exception as e:
        return f"❌ Error generating catch-up summary: {e}"


def main():
    """Command line interface for slash commands."""
    if len(sys.argv) < 2:
        print("Usage: uv run slash_commands.py <command> [arguments]")
        print("\nAvailable commands:")
        print("  summarize [streams] [hours]    - Daily summary")
        print("  prepare [streams] [days]       - Morning briefing") 
        print("  catch_up [streams] [hours]     - Catch-up summary")
        print("\nExamples:")
        print("  uv run slash_commands.py summarize")
        print("  uv run slash_commands.py prepare general,dev 5")
        print("  uv run slash_commands.py catch_up general 4")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    arguments = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    
    if command == "summarize":
        result = zulipchat_summarize(arguments)
    elif command == "prepare":
        result = zulipchat_prepare(arguments)
    elif command == "catch_up":
        result = zulipchat_catch_up(arguments)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    print("\n" + result)


if __name__ == "__main__":
    main()