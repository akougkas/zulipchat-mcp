# Zulip MCP Enhancement Plan - Priority Features

## Current Implementation Review

Based on the IMPLEMENTATION-REPORT.md, the recent work delivered:
- ✅ **Event Listener**: Basic implementation exists with queue registration and long-polling
- ✅ **DatabaseManager**: Abstraction layer implemented
- ✅ **AFK-gated notifications**: Smart routing based on user state
- ✅ **Topic scheme**: Organized as `Agents/Chat|Input|Status/<project>/<context>`
- ✅ **Dual identity**: Bot for agent operations, user for personal messages

However, the event listener is limited to Agent-Channel monitoring and doesn't expose general event streaming to MCP tools.

## Priority 1: Event Streaming Enhancement

### Current State
- MessageListener exists but only monitors Agent-Channel
- Long-polling with 30s timeout implemented
- Auto-reconnect on queue expiry works

### Required Enhancements

```python
# New tool: src/zulipchat_mcp/tools/events.py

def subscribe_to_events(
    event_types: list[str] | None = None,  # ["message", "subscription", "presence"]
    narrow: list[dict] | None = None,      # [{"operator": "stream", "operand": "general"}]
    all_public_streams: bool = False,
) -> dict[str, Any]:
    """Register an event queue for real-time updates."""
    # Use existing MessageListener infrastructure
    # Return queue_id for polling
    
def poll_events(
    queue_id: str,
    last_event_id: int = -1,
    wait_time: int = 30,  # Seconds to wait
) -> dict[str, Any]:
    """Poll for new events from a registered queue."""
    # Return events since last_event_id
    # Auto-handle queue expiry/re-registration
```

### Integration with Existing Listener
- Extend MessageListener to support multiple queues
- Add event type filtering beyond just Agent-Channel
- Store queue registrations in database

## Priority 2: Enhanced Message Options

### Current get_messages Limitations
- No `narrow` parameter for filtering
- No `anchor` flexibility
- Missing `local_id` and `queue_id` support

### Required Changes to `tools/messaging.py`

```python
def get_messages(
    # ADD: Flexible anchoring
    anchor: str | int = "newest",  # "newest", "oldest", "first_unread", or message_id
    num_before: int = 0,
    num_after: int = 100,
    # ADD: Powerful narrow filtering
    narrow: list[dict] | None = None,
    # Examples:
    # [{"operator": "stream", "operand": "general"}]
    # [{"operator": "topic", "operand": "project updates"}]
    # [{"operator": "sender", "operand": "user@example.com"}]
    # [{"operator": "is", "operand": "starred"}]
    include_anchor: bool = True,
    client_gravatar: bool = True,
    apply_markdown: bool = True,
) -> dict[str, Any]:
    """Get messages with advanced filtering."""
    # Implementation: Pass narrow directly to Zulip API
    
def send_message(
    message_type: str,
    to: str,
    content: str,
    topic: str | None = None,
    # ADD: Client-side message tracking
    queue_id: str | None = None,    # For local echo
    local_id: str | None = None,    # Client deduplication
    read_by_sender: bool = True,    # Auto-mark as read
) -> dict[str, Any]:
    """Send message with client tracking support."""
```

### Narrow Operators to Support
```python
NARROW_OPERATORS = {
    "stream": "Filter by stream name",
    "topic": "Filter by topic",
    "sender": "Filter by sender email",
    "is": "Filter by flag (starred, mentioned, alerted)",
    "near": "Messages near a specific message ID",
    "id": "Specific message IDs",
    "has": "Has property (link, image, attachment)",
    "search": "Full-text search",
}
```

## Priority 3: Bulk Operations

### New Tool: `tools/bulk_ops.py`

```python
def bulk_update_messages(
    operation: Literal["add_flag", "remove_flag", "mark_read", "mark_unread"],
    # Target messages
    message_ids: list[int] | None = None,
    narrow: list[dict] | None = None,  # Or use narrow to select
    # Flag operations
    flag: Literal["read", "starred", "collapsed", "mentioned"] | None = None,
) -> dict[str, Any]:
    """Bulk update message flags/status."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "bulk_update_messages"}):
        track_tool_call("bulk_update_messages")
        try:
            client = _get_client()
            
            if operation in ["mark_read", "mark_unread"]:
                flag = "read"
                operation = "add_flag" if operation == "mark_read" else "remove_flag"
            
            # Use Zulip's update_message_flags endpoint
            result = client.client.update_message_flags(
                op=operation,
                flag=flag,
                messages=message_ids,
                narrow=narrow
            )
            
            return {
                "status": "success",
                "messages_updated": result.get("messages", []),
                "count": len(result.get("messages", []))
            }
        except Exception as e:
            track_tool_error("bulk_update_messages", type(e).__name__)
            return {"status": "error", "error": str(e)}

def mark_all_as_read(
    stream: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Mark all messages as read in scope."""
    narrow = []
    if stream:
        narrow.append({"operator": "stream", "operand": stream})
    if topic:
        narrow.append({"operator": "topic", "operand": topic})
    
    return bulk_update_messages(
        operation="mark_read",
        narrow=narrow if narrow else None
    )
```

### Integration
- Register in `server.py` as new tool group
- Use existing client infrastructure
- Leverage narrow for selection

## Priority 4: Topic Management

### Enhance `tools/streams.py`

```python
def manage_topic(
    stream: str,
    topic: str,
    action: Literal["mute", "unmute", "delete", "move"],
    # For move operation
    new_topic: str | None = None,
    new_stream: str | None = None,
    # Options
    propagate_mode: Literal["change_one", "change_later", "change_all"] = "change_all",
) -> dict[str, Any]:
    """Manage stream topics."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "manage_topic"}):
        track_tool_call("manage_topic")
        try:
            client = _get_client()
            
            if action == "mute":
                result = client.client.mute_topic({
                    "stream": stream,
                    "topic": topic,
                    "op": "add"
                })
            elif action == "unmute":
                result = client.client.mute_topic({
                    "stream": stream,
                    "topic": topic,
                    "op": "remove"
                })
            elif action == "delete":
                # Delete all messages in topic
                result = client.client.delete_topic({
                    "stream_id": _get_stream_id(stream),
                    "topic_name": topic
                })
            elif action == "move":
                # Move topic to new location
                # First get messages in topic
                messages = client.get_messages_raw(
                    narrow=[
                        {"operator": "stream", "operand": stream},
                        {"operator": "topic", "operand": topic}
                    ],
                    num_before=0,
                    num_after=1000
                )
                
                if messages.get("messages"):
                    # Edit first message to move entire topic
                    first_msg = messages["messages"][0]
                    result = client.edit_message(
                        first_msg["id"],
                        topic=new_topic,
                        stream_id=_get_stream_id(new_stream) if new_stream else None,
                        propagate_mode=propagate_mode
                    )
                else:
                    return {"status": "error", "error": "No messages in topic"}
            
            return {"status": "success", "action": action, "topic": topic}
            
        except Exception as e:
            track_tool_error("manage_topic", type(e).__name__)
            return {"status": "error", "error": str(e)}

def get_stream_topics(
    stream: str,
    include_muted: bool = True,
) -> dict[str, Any]:
    """Get all topics in a stream."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_stream_topics"}):
        track_tool_call("get_stream_topics")
        try:
            client = _get_client()
            stream_id = _get_stream_id(stream)
            
            result = client.client.get_stream_topics(stream_id)
            
            topics = result.get("topics", [])
            if not include_muted:
                # Filter out muted topics
                muted = client.client.get_muted_topics().get("muted_topics", [])
                muted_set = {(m["stream"], m["topic"]) for m in muted}
                topics = [t for t in topics if (stream, t["name"]) not in muted_set]
            
            return {
                "status": "success",
                "stream": stream,
                "topics": topics,
                "count": len(topics)
            }
            
        except Exception as e:
            track_tool_error("get_stream_topics", type(e).__name__)
            return {"status": "error", "error": str(e)}
```

## Priority 5: Scheduled Messages

### New Tool: `tools/scheduling.py`

```python
from datetime import datetime, timezone
from typing import Any

def schedule_message(
    message_type: Literal["direct", "stream"],
    to: str | list[str],
    content: str,
    scheduled_delivery_timestamp: int | datetime | str,  # Unix timestamp or ISO string
    topic: str | None = None,
) -> dict[str, Any]:
    """Schedule a message for future delivery."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "schedule_message"}):
        track_tool_call("schedule_message")
        try:
            client = _get_client()
            
            # Convert timestamp to Unix timestamp
            if isinstance(scheduled_delivery_timestamp, str):
                # Parse ISO format
                dt = datetime.fromisoformat(scheduled_delivery_timestamp)
                timestamp = int(dt.timestamp())
            elif isinstance(scheduled_delivery_timestamp, datetime):
                timestamp = int(scheduled_delivery_timestamp.timestamp())
            else:
                timestamp = scheduled_delivery_timestamp
            
            # Validate future time
            if timestamp <= int(datetime.now(timezone.utc).timestamp()):
                return {"status": "error", "error": "Scheduled time must be in the future"}
            
            result = client.client.create_scheduled_message({
                "type": message_type,
                "to": to if isinstance(to, list) else [to],
                "content": content,
                "topic": topic,
                "scheduled_delivery_timestamp": timestamp
            })
            
            return {
                "status": "success",
                "scheduled_message_id": result.get("scheduled_message_id"),
                "scheduled_for": datetime.fromtimestamp(timestamp).isoformat()
            }
            
        except Exception as e:
            track_tool_error("schedule_message", type(e).__name__)
            return {"status": "error", "error": str(e)}

def get_scheduled_messages() -> dict[str, Any]:
    """Get all scheduled messages."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_scheduled_messages"}):
        track_tool_call("get_scheduled_messages")
        try:
            client = _get_client()
            result = client.client.get_scheduled_messages()
            
            messages = result.get("scheduled_messages", [])
            return {
                "status": "success",
                "scheduled_messages": messages,
                "count": len(messages)
            }
            
        except Exception as e:
            track_tool_error("get_scheduled_messages", type(e).__name__)
            return {"status": "error", "error": str(e)}

def cancel_scheduled_message(
    scheduled_message_id: int
) -> dict[str, Any]:
    """Cancel a scheduled message."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "cancel_scheduled_message"}):
        track_tool_call("cancel_scheduled_message")
        try:
            client = _get_client()
            result = client.client.delete_scheduled_message(scheduled_message_id)
            
            return {"status": "success", "message": "Scheduled message cancelled"}
            
        except Exception as e:
            track_tool_error("cancel_scheduled_message", type(e).__name__)
            return {"status": "error", "error": str(e)}
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. **Enhance get_messages** with narrow parameter
2. **Add send_message** tracking (queue_id, local_id)
3. Test narrow operators comprehensively

### Phase 2: Bulk & Topics (Week 1)
1. **Create bulk_ops.py** with mark as read/unread
2. **Enhance streams.py** with topic management
3. Test bulk operations on large message sets

### Phase 3: Scheduling (Week 2)
1. **Create scheduling.py** with all 3 functions
2. Add timezone handling
3. Test scheduled message lifecycle

### Phase 4: Event Streaming (Week 2)
1. **Create events.py** building on MessageListener
2. Support multiple event queues
3. Test reconnection and event filtering

## File Changes Summary

### New Files
- `src/zulipchat_mcp/tools/events.py` - Event streaming tools
- `src/zulipchat_mcp/tools/bulk_ops.py` - Bulk message operations
- `src/zulipchat_mcp/tools/scheduling.py` - Scheduled messages

### Modified Files
- `src/zulipchat_mcp/tools/messaging.py` - Add narrow, queue_id, local_id
- `src/zulipchat_mcp/tools/streams.py` - Add topic management
- `src/zulipchat_mcp/server.py` - Register new tool groups

### Total New Tools: 13
- Event streaming: 2 (subscribe_to_events, poll_events)
- Bulk operations: 2 (bulk_update_messages, mark_all_as_read)
- Topic management: 2 (manage_topic, get_stream_topics)
- Scheduling: 3 (schedule_message, get_scheduled_messages, cancel_scheduled_message)
- Enhanced existing: 4 (get_messages, send_message with new params)

This brings us from 24 to 37 tools, covering the most critical Zulip API gaps.