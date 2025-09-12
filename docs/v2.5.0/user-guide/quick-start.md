# Quick Start Guide

Get up and running with ZulipChat MCP v2.5.0 in minutes. This guide covers basic usage patterns and common operations.

## Prerequisites

Before starting, ensure you have:

- ✅ [Installed ZulipChat MCP](installation.md)
- ✅ [Configured Zulip credentials](configuration.md)
- ✅ Active Zulip organization access
- ✅ Basic familiarity with MCP protocol

## Starting the Server

### Basic Server Start

```bash
# Using environment variables (recommended)
export ZULIP_EMAIL="your@email.com"
export ZULIP_API_KEY="your_api_key"
export ZULIP_SITE="https://yourorg.zulipchat.com"

python -m zulipchat_mcp.server
```

### With Debug Logging

```bash
python -m zulipchat_mcp.server --debug
```

### Expected Output

```
[INFO] ZulipChat MCP v2.5.0 starting...
[INFO] Identity: User (your@email.com)
[INFO] Connected to: Your Organization (yourorg.zulipchat.com)  
[INFO] Available tools: 23 (7 categories)
[INFO] Server running on localhost:3000
[INFO] Ready for MCP connections
```

## Basic Usage Examples

### 1. Send Your First Message

```python
# Send a message to a stream
result = await message(
    operation="send",
    type="stream", 
    to="general",
    content="Hello from ZulipChat MCP!",
    topic="test"
)

print(f"Message sent: ID {result['id']}")
```

### 2. List Available Streams

```python
# Get streams you can access
result = await manage_streams(operation="list")

for stream in result["streams"]:
    print(f"Stream: {stream['name']} (ID: {stream['stream_id']})")
```

### 3. Search Messages

```python
# Search for recent messages in a stream
result = await search_messages(
    narrow=[
        {"operator": "stream", "operand": "general"},
        {"operator": "search", "operand": "python"}
    ],
    limit=10
)

print(f"Found {len(result['messages'])} messages")
```

### 4. Get User Information

```python
# Get information about yourself
result = await manage_users(operation="get", user_id="me")

print(f"Hello {result['full_name']}!")
print(f"Role: {result['role']}")
```

## Identity Management

ZulipChat MCP supports three identity types. Here's how to work with them:

### Checking Current Identity

```python
# See what identity you're using
result = await switch_identity("status")

print(f"Current identity: {result['current_identity']}")
print(f"Capabilities: {', '.join(result['capabilities'])}")
```

### Using Bot Identity (if configured)

```python
# Switch to bot identity for automation
await switch_identity("bot")

# Send an automated message
await message(
    operation="send",
    type="stream",
    to="bot-testing", 
    content="🤖 Automated message from bot",
    topic="automation"
)

# Switch back to user identity
await switch_identity("user")
```

## Common Workflows

### Workflow 1: Stream Management

```python
# Create a new project stream
result = await manage_streams(
    operation="create",
    stream_names=["project-alpha"],
    properties={
        "description": "Alpha project coordination",
        "is_private": False,
        "announce": True
    }
)

# Set up initial topic
await message(
    operation="send",
    type="stream",
    to="project-alpha",
    content="Welcome to Project Alpha! 🚀",
    topic="kickoff"
)

# Get analytics for the stream
analytics = await stream_analytics(
    stream_name="project-alpha",
    include_user_activity=True
)
```

### Workflow 2: Real-time Event Monitoring

```python
# Register for real-time events
queue = await register_events(
    event_types=["message", "reaction"],
    narrow=[{"operator": "stream", "operand": "general"}]
)

print(f"Event queue registered: {queue['queue_id']}")

# Poll for events
while True:
    events = await get_events(
        queue_id=queue["queue_id"],
        last_event_id=queue.get("last_event_id", -1)
    )
    
    for event in events.get("events", []):
        if event["type"] == "message":
            msg = event["message"]
            print(f"New message from {msg['sender_full_name']}: {msg['content']}")
    
    # Update last event ID for next poll
    if events.get("events"):
        queue["last_event_id"] = events["events"][-1]["id"]
```

### Workflow 3: File Upload and Sharing

```python
# Upload a file
with open("report.pdf", "rb") as file:
    result = await upload_file(
        file_data=file.read(),
        filename="monthly-report.pdf"
    )

# Share the file in a message
await message(
    operation="send",
    type="stream",
    to="team-updates",
    content=f"Monthly report is ready: [report.pdf]({result['url']})",
    topic="reports"
)
```

### Workflow 4: Advanced Search with Analytics

```python
# Perform advanced search
results = await advanced_search(
    query="python OR javascript",
    search_filters=[
        {"operator": "stream", "operand": "development"},
        {"operator": "after", "operand": "2024-01-01"}
    ],
    include_content_analysis=True,
    cache_results=True
)

# Get analytics on search results
analytics = await analytics(
    search_results=results,
    metrics=["message_count", "user_activity", "topic_distribution"],
    generate_insights=True
)

print(f"Analysis: {analytics['insights']}")
```

## Progressive Parameter Usage

ZulipChat MCP supports progressive disclosure - start simple, add complexity as needed.

### Basic → Advanced → Expert

```python
# BASIC: Simple message send
await message("send", "stream", "general", "Hello!")

# ADVANCED: With topic and formatting  
await message(
    "send", "stream", "general", 
    "**Bold** message with topic",
    topic="important"
)

# EXPERT: Full control with scheduling and cross-posting
await message(
    operation="send",
    type="stream", 
    to="announcements",
    content="📢 **System Maintenance**\n\nScheduled downtime: 2AM-4AM UTC",
    topic="maintenance",
    schedule_at=datetime(2024, 2, 1, 2, 0),
    cross_post_streams=["general", "development"],
    disable_notifications=False
)
```

## Testing Your Setup

### Health Check

```python
# Verify server health
from zulipchat_mcp.utils.health import perform_health_check

health = await perform_health_check()
print(f"Server status: {health['status']}")

if health['status'] != 'healthy':
    print("Issues found:")
    for check, details in health['checks'].items():
        if not details['healthy']:
            print(f"  - {check}: {details['status']}")
```

### Connection Test

```python
# Test basic Zulip connectivity
result = await manage_users(operation="get", user_id="me")
if result.get("status") == "success":
    print("✅ Zulip connection working")
    print(f"Connected as: {result['full_name']}")
else:
    print("❌ Connection issue:", result.get("error"))
```

## MCP Client Integration

### Claude Code Integration

If using with Claude Code, the server will automatically:

1. **Register tools** with proper descriptions
2. **Handle identity management** seamlessly  
3. **Provide error context** for debugging
4. **Cache results** for performance

### Custom MCP Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "zulipchat_mcp.server"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")
            
            # Call a tool
            result = await session.call_tool(
                "messaging.message",
                {
                    "operation": "send",
                    "type": "stream", 
                    "to": "test",
                    "content": "Hello from MCP client!"
                }
            )
            print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Error Handling

### Common Patterns

```python
# Basic error handling
result = await message("send", "stream", "general", "Hello!")

if result.get("status") == "error":
    print(f"Error: {result['error']}")
    if "rate limit" in result["error"].lower():
        print("Rate limited - waiting before retry...")
        await asyncio.sleep(60)
else:
    print("Message sent successfully!")

# Advanced error handling with retries
from zulipchat_mcp.core.error_handling import get_error_handler

handler = get_error_handler()
result = await handler.execute_with_retry(
    lambda: message("send", "stream", "general", "Retry test"),
    operation_name="send_message"
)
```

## Performance Tips

### Caching

```python
# Enable caching for repeated operations
streams = await manage_streams("list", use_cache=True)

# Cache search results for analytics
search_results = await advanced_search(
    query="monthly report",
    cache_results=True,
    cache_ttl=300  # 5 minutes
)
```

### Bulk Operations

```python
# Use bulk operations for efficiency
await bulk_operations(
    operation="mark_read",
    narrow=[{"operator": "stream", "operand": "general"}]
)

# Batch message sends (when available)
messages = [
    {"to": "stream1", "content": "Message 1"},
    {"to": "stream2", "content": "Message 2"}
]
# await bulk_send_messages(messages)  # Future feature
```

## Next Steps

Now that you're up and running:

1. **Explore [API Reference](../api-reference/)** - Detailed function documentation
2. **Review [Tool Categories](../developer-guide/tool-categories.md)** - Understand the 7 tool groups  
3. **Check [Migration Guide](../migration-guide.md)** - If upgrading from legacy tools
4. **Read [Troubleshooting](../troubleshooting.md)** - Common issues and solutions

## Example Scripts

### Daily Standup Bot

```python
import asyncio
from datetime import datetime, timedelta

async def daily_standup():
    # Switch to bot identity
    await switch_identity("bot")
    
    # Post standup reminder
    await message(
        "send", "stream", "team",
        "🌅 **Daily Standup Reminder**\n\n" + 
        "Time for our daily standup! Please share:\n" +
        "• What did you work on yesterday?\n" +
        "• What will you work on today?\n" +
        "• Any blockers?",
        topic="standup"
    )
    
    # Schedule tomorrow's reminder
    tomorrow = datetime.now() + timedelta(days=1)
    await message(
        "schedule", "stream", "team",
        "🌅 Daily Standup Reminder - Scheduled",
        topic="standup",
        schedule_at=tomorrow.replace(hour=9, minute=0)
    )

# Run daily
asyncio.run(daily_standup())
```

### Stream Health Monitor

```python
async def monitor_stream_health():
    streams = await manage_streams("list")
    
    for stream in streams["streams"]:
        analytics = await stream_analytics(
            stream_id=stream["stream_id"],
            include_user_activity=True
        )
        
        # Check for inactive streams
        if analytics["recent_activity"]["message_count_7d"] == 0:
            print(f"⚠️  Inactive stream: {stream['name']}")
            
        # Check for high activity
        elif analytics["recent_activity"]["message_count_24h"] > 100:
            print(f"🔥 High activity stream: {stream['name']}")

asyncio.run(monitor_stream_health())
```

---

**You're ready to use ZulipChat MCP!** 

For detailed API documentation, continue to [API Reference](../api-reference/) or explore specific [Tool Categories](../developer-guide/tool-categories.md).