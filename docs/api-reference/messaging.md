# Messaging API Reference

The messaging category provides comprehensive message operations including sending, scheduling, editing, searching, and bulk operations. All functions are identity-aware and support advanced Zulip features.

## Tool Overview

| Function | Purpose | Identity Support |
|----------|---------|------------------|
| [`message()`](#message) | Send, schedule, or draft messages | User, Bot, Admin |
| [`search_messages()`](#search_messages) | Search and retrieve messages with filtering | User, Bot, Admin |
| [`edit_message()`](#edit_message) | Edit message content, topics, or move between streams | User, Admin |
| [`bulk_operations()`](#bulk_operations) | Perform bulk actions on multiple messages | User, Bot, Admin |
| [`message_history()`](#message_history) | Get message history and edit information | User, Admin |
| [`cross_post_message()`](#cross_post_message) | Share messages across multiple streams | User, Bot |
| [`add_reaction()`](#add_reaction) | Add emoji reaction to a message | User, Bot |
| [`remove_reaction()`](#remove_reaction) | Remove emoji reaction from a message | User, Bot |

## Functions

### `message()`

Send, schedule, or draft messages with full formatting support.

#### Signature
```python
async def message(
    operation: Literal["send", "schedule", "draft"],
    type: Literal["stream", "private"],
    to: str | list[str],
    content: str,
    topic: str | None = None,
    # Scheduled messaging
    schedule_at: datetime | None = None,
    # Advanced parameters (optional)
    queue_id: str | None = None,
    local_id: str | None = None,
    read_by_sender: bool = True,
    # Formatting options
    syntax_highlight: bool = False,
    link_preview: bool = True,
    emoji_translate: bool = True,
) -> MessageResponse
```

#### Parameters

##### Required Parameters
- **`operation`** (Literal["send", "schedule", "draft"]): Type of operation
  - `"send"`: Send message immediately
  - `"schedule"`: Schedule for future delivery (requires `schedule_at`)
  - `"draft"`: Create a draft message
- **`type`** (Literal["stream", "private"]): Message type
  - `"stream"`: Stream message (public)
  - `"private"`: Private message (direct or group)
- **`to`** (str | list[str]): Recipient(s)
  - For stream: stream name (e.g., "general")
  - For private: user email or list of emails
- **`content`** (str): Message content in Markdown format

##### Optional Parameters
- **`topic`** (str | None): Topic for stream messages (required for stream type)
- **`schedule_at`** (datetime | None): When to send scheduled messages (required for operation="schedule")
- **`queue_id`** (str | None): Event queue ID for message association
- **`local_id`** (str | None): Client-side ID for deduplication
- **`read_by_sender`** (bool): Whether message is marked as read by sender (default: True)
- **`syntax_highlight`** (bool): Enable syntax highlighting for code blocks (default: False)
- **`link_preview`** (bool): Enable automatic link previews (default: True)
- **`emoji_translate`** (bool): Enable emoji code translation (default: True)

#### Usage Examples

**Send immediate message**:
```python
# Send to stream
result = await message("send", "stream", "general", "Hello world!", topic="greetings")

# Send private message
result = await message("send", "private", "user@example.com", "Hi there!")

# Send to multiple users
result = await message("send", "private", ["user1@example.com", "user2@example.com"], "Team update")
```

**Schedule message**:
```python
# Schedule for later
result = await message(
    "schedule", 
    "stream", 
    "announcements", 
    "Meeting reminder",
    topic="meetings", 
    schedule_at=datetime(2024, 1, 15, 14, 0)
)
```

**Create draft**:
```python
# Create draft message
result = await message("draft", "private", "user@example.com", "Draft message content")
```

**Advanced formatting options**:
```python
# Message with code syntax highlighting
result = await message(
    "send",
    "stream",
    "development",
    "```python\ndef hello():\n    print('Hello')\n```",
    topic="code-examples",
    syntax_highlight=True,
    link_preview=False
)
```

#### Response Format

**Successful send**:
```python
{
    "status": "success",
    "message_id": 123456,
    "operation": "send",
    "timestamp": "2024-01-15T10:30:00.000000"
}
```

**Successful schedule**:
```python
{
    "status": "success",
    "operation": "schedule",
    "scheduled_message_id": 789,
    "scheduled_at": "2024-01-15T14:00:00",
    "message": "Message scheduled successfully",
    "timestamp": "2024-01-15T10:30:00.000000"
}
```

**Successful draft**:
```python
{
    "status": "success",
    "operation": "draft",
    "draft_id": "draft_1705312200000",
    "draft_data": {
        "draft_id": "draft_1705312200000",
        "type": "private",
        "to": "user@example.com",
        "content": "Draft message content",
        "topic": null,
        "created_at": "2024-01-15T10:30:00.000000",
        "last_modified": "2024-01-15T10:30:00.000000"
    },
    "message": "Draft message created",
    "note": "Draft stored locally - use draft_data to recreate message when ready to send"
}
```

**Error response**:
```python
{
    "status": "error",
    "error": "Topic is required for stream messages",
    "operation": "send"
}
```

### `search_messages()`

Search and retrieve messages with powerful filtering capabilities.

#### Signature
```python
async def search_messages(
    narrow: list[NarrowFilter | dict[str, Any]] | None = None,
    anchor: int | Literal["newest", "oldest", "first_unread"] = "newest",
    num_before: int = 50,
    num_after: int = 50,
    include_anchor: bool = True,
    use_first_unread_anchor: bool = False,
    apply_markdown: bool = True,
    client_gravatar: bool = False,
) -> MessageList
```

#### Parameters

##### Optional Parameters
- **`narrow`** (list[NarrowFilter | dict] | None): List of narrow filters for message filtering
  - Format: `[{"operator": "stream", "operand": "general"}]`
  - Common operators: `stream`, `topic`, `sender`, `search`, `has`, `is`
- **`anchor`** (int | Literal["newest", "oldest", "first_unread"]): Starting point for search (default: "newest")
  - Can be a message ID or one of the special anchors
- **`num_before`** (int): Number of messages before anchor to retrieve (default: 50)
- **`num_after`** (int): Number of messages after anchor to retrieve (default: 50)
- **`include_anchor`** (bool): Whether to include the anchor message (default: True)
- **`use_first_unread_anchor`** (bool): Use first unread as anchor if available (default: False)
- **`apply_markdown`** (bool): Apply markdown rendering to message content (default: True)
- **`client_gravatar`** (bool): Use client-side gravatar rendering (default: False)

#### Narrow Filter Examples

**Stream and Topic Filters**:
```python
# Messages from specific stream
narrow = [{"operator": "stream", "operand": "general"}]

# Messages from stream with specific topic
narrow = [
    {"operator": "stream", "operand": "development"},
    {"operator": "topic", "operand": "bug-fixes"}
]
```

**Content Search**:
```python
# Search message content
narrow = [{"operator": "search", "operand": "python deployment"}]

# Combine with stream filter
narrow = [
    {"operator": "stream", "operand": "general"},
    {"operator": "search", "operand": "meeting notes"}
]
```

**Message Attributes**:
```python
# Messages with attachments
narrow = [{"operator": "has", "operand": "attachment"}]

# Messages with reactions
narrow = [{"operator": "has", "operand": "reaction"}]

# Messages with links
narrow = [{"operator": "has", "operand": "link"}]
```

**User Filters**:
```python
# Messages from specific user
narrow = [{"operator": "sender", "operand": "alice@example.com"}]

# Private messages with specific user
narrow = [{"operator": "pm-with", "operand": "bob@example.com"}]
```

#### Usage Examples

**Get recent messages from a stream**:
```python
result = await search_messages(
    narrow=[{"operator": "stream", "operand": "general"}],
    num_before=0,
    num_after=100
)
```

**Search for messages with text**:
```python
result = await search_messages(
    narrow=[
        {"operator": "stream", "operand": "development"},
        {"operator": "search", "operand": "bug fix"}
    ],
    anchor="newest",
    num_before=50,
    num_after=50
)
```

**Get unread messages**:
```python
result = await search_messages(
    narrow=[{"operator": "is", "operand": "unread"}],
    anchor="first_unread",
    use_first_unread_anchor=True,
    num_before=0,
    num_after=100
)
```

**Get messages around a specific message ID**:
```python
result = await search_messages(
    narrow=[{"operator": "stream", "operand": "general"}],
    anchor=123456,  # specific message ID
    num_before=10,
    num_after=10,
    include_anchor=True
)
```

#### Response Format

```python
{
    "status": "success",
    "messages": [
        {
            "id": 123456,
            "sender": "User Name",
            "email": "user@example.com",
            "timestamp": 1705312200,
            "content": "Message content here (truncated if > 50KB)",
            "type": "stream",
            "stream": "general",
            "topic": "discussions",
            "reactions": [
                {
                    "emoji_name": "thumbs_up",
                    "user_id": [789]
                }
            ],
            "flags": ["read"],
            "last_edit_timestamp": null
        }
    ],
    "count": 25,
    "anchor": 123456,
    "found_anchor": true,
    "found_newest": false,
    "found_oldest": false,
    "history_limited": false,
    "narrow": [{"operator": "stream", "operand": "general"}]
}
```

**Error response**:
```python
{
    "status": "error",
    "error": "Invalid message ID for anchor"
}
```

### `edit_message()`

Edit or move messages with topic management capabilities.

#### Signature
```python
async def edit_message(
    message_id: int,
    content: str | None = None,
    topic: str | None = None,
    stream_id: int | None = None,
    propagate_mode: Literal["change_one", "change_later", "change_all"] = "change_one",
    send_notification_to_old_thread: bool = False,
    send_notification_to_new_thread: bool = True,
) -> EditResponse
```

#### Parameters

##### Required Parameters
- **`message_id`** (int): ID of the message to edit

##### Optional Parameters (at least one required)
- **`content`** (str | None): New message content
- **`topic`** (str | None): New topic name
- **`stream_id`** (int | None): New stream ID for moving between streams
- **`propagate_mode`** (Literal["change_one", "change_later", "change_all"]): How to propagate topic changes
  - `"change_one"`: Change only this message (default)
  - `"change_later"`: Change this and later messages
  - `"change_all"`: Change all messages in topic
- **`send_notification_to_old_thread`** (bool): Send notification to original thread (default: False)
- **`send_notification_to_new_thread`** (bool): Send notification to new thread (default: True)

#### Usage Examples

**Edit message content**:
```python
result = await edit_message(
    message_id=123456,
    content="Updated message content with corrections"
)
```

**Change topic for single message**:
```python
result = await edit_message(
    message_id=123456,
    topic="new-topic-name"
)
```

**Change topic and propagate to all messages**:
```python
result = await edit_message(
    message_id=123456,
    topic="renamed-discussion",
    propagate_mode="change_all"
)
```

**Move message to different stream**:
```python
result = await edit_message(
    message_id=123456,
    stream_id=789,
    topic="moved-discussion",
    send_notification_to_old_thread=True
)
```

#### Response Format

```python
{
    "status": "success",
    "message": "Message edited successfully",
    "message_id": 123456,
    "changes": ["content", "topic"],
    "propagate_mode": "change_one",
    "timestamp": "2024-01-15T10:30:00.000000"
}
```

**Error response**:
```python
{
    "status": "error",
    "error": "Must provide content, topic, or stream_id to edit",
    "message_id": 123456
}
```

### `bulk_operations()`

Perform bulk operations on multiple messages, now with intelligent batch processing for non-native bulk actions.

#### Signature
```python
async def bulk_operations(
    operation: Literal["mark_read", "mark_unread", "add_flag", "remove_flag", "add_reaction", "remove_reaction", "delete_messages"],
    # Message Selection
    stream: str | None = None,
    topic: str | None = None,
    sender: str | None = None,
    narrow: list[NarrowFilter | dict[str, Any]] | None = None,
    message_ids: list[int] | None = None,
    # Operation-specific parameters
    flag: str | None = None,
    emoji_name: str | None = None,
    emoji_code: str | None = None,
    reaction_type: Literal["unicode_emoji", "realm_emoji", "zulip_extra_emoji"] | None = None,
    # Batch processing parameters
    progress_callback: Callable[[ProgressReport], None] | None = None,
) -> BulkResponse
```

#### Parameters

##### Required Parameters
- **`operation`** (Literal): Type of bulk operation.

##### Message Selection (one method required)
- **Simple Selection**:
  - `stream` (str | None): Stream name.
  - `topic` (str | None): Topic name.
  - `sender` (str | None): Sender email.
- **Advanced Selection**:
  - `narrow` (list | None): Narrow filters to select messages.
  - `message_ids` (list[int] | None): Explicit list of message IDs.

##### Operation-Specific Parameters
- **`flag`** (str | None): Flag name for `add_flag`/`remove_flag` (e.g., "starred").
- **`emoji_name`** (str | None): Emoji name for `add_reaction`/`remove_reaction`.
- **`emoji_code`** (str | None): Emoji code for custom emojis.
- **`reaction_type`** (Literal | None): Type of reaction (default: "unicode_emoji").

##### Batch Processing
- **`progress_callback`** (Callable | None): A function to receive `ProgressReport` objects during long-running batch operations (like reactions or deletions).

#### New: Batch Processing and Progress Reporting
For operations that are not natively supported in bulk by Zulip (`add_reaction`, `remove_reaction`, `delete_messages`), this tool now uses an intelligent `BatchProcessor`. This system automatically handles rate limiting, adaptive batch sizing, and retries.

You can monitor the progress of these operations by providing a `progress_callback` function.

**Example of a `progress_callback` function:**
```python
def my_progress_reporter(report):
    print(f"Progress: {report.percent_complete:.1f}% complete. "
          f"Rate: {report.current_rate:.1f} items/sec. "
          f"ETA: {report.estimated_time_remaining}")
```

#### Usage Examples

**Mark all messages in a stream as read**:
```python
result = await bulk_operations("mark_read", stream="general")
```

**Add star flag to specific messages**:
```python
result = await bulk_operations(
    "add_flag",
    message_ids=[123, 456, 789],
    flag="starred"
)
```

**Add reactions to many messages with progress reporting**:
```python
result = await bulk_operations(
    "add_reaction",
    narrow=[{"operator": "stream", "operand": "community"}],
    emoji_name="rocket",
    progress_callback=my_progress_reporter
)
```

**Delete messages from a user**:
```python
result = await bulk_operations(
    "delete_messages",
    sender="spammer@example.com"
)
```

#### Response Format

**Successful Native Bulk Operation**:
```python
{
    "status": "success",
    "message": "Successfully marked as read",
    "affected_count": 42,
    "operation": "mark_read",
    "timestamp": "2025-09-13T10:30:00.000000"
}
```

**Batch-Processed Operation Response**:
```python
{
    "status": "completed", // or "partial", "failed"
    "message": "Operation add_reaction completed.",
    "affected_count": 95,
    "successful_items": [101, 102, 103, ...], // First 10 successful IDs
    "failed_items": [
        {"item": 201, "error": "Message not found"}
    ], // First 5 failed items
    "operation": "add_reaction",
    "timestamp": "2025-09-13T10:30:00.000000"
}
```

**Error response**:
```python
{
    "status": "error",
    "error": "Must provide a message selection method.",
    "operation": "mark_read"
}
```

### `message_history()`

Get comprehensive message history and edit tracking.

#### Signature
```python
async def message_history(
    message_id: int,
    include_content_history: bool = True,
    include_edit_history: bool = True,
    include_reaction_history: bool = False,
) -> dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`message_id`** (int): ID of the message to get history for

##### Optional Parameters
- **`include_content_history`** (bool): Include previous versions of message content (default: True)
- **`include_edit_history`** (bool): Include edit timestamps and user information (default: True)
- **`include_reaction_history`** (bool): Include reaction addition/removal history (default: False)

#### Usage Examples

**Get full message history**:
```python
result = await message_history(
    message_id=123456,
    include_content_history=True,
    include_edit_history=True
)
```

**Get only edit history**:
```python
result = await message_history(
    message_id=123456,
    include_content_history=False,
    include_edit_history=True
)
```

**Get all available history data**:
```python
result = await message_history(
    message_id=123456,
    include_content_history=True,
    include_edit_history=True,
    include_reaction_history=True
)
```

#### Response Format

```python
{
    "status": "success",
    "message_id": 123456,
    "original_timestamp": 1705312200,
    "sender": "User Name",
    "sender_email": "user@example.com",
    "current_content": "Current message content",
    "stream_id": 123,
    "topic": "discussions",
    
    # Edit history (if requested)
    "edit_history": [
        {
            "timestamp": 1705312800,
            "edit_type": "content_or_topic_change",
            "note": "Message was edited (specific changes not available via API)"
        }
    ],
    "total_edits": 1,
    
    # Content history (if requested)
    "content_history": {
        "note": "Full content history not available via Zulip API",
        "current_version": "Current message content",
        "has_been_edited": true
    },
    
    # Reaction history (if requested)
    "reaction_history": {
        "current_reactions": [
            {"emoji_name": "thumbs_up", "user_id": [789]}
        ],
        "total_reactions": 1,
        "reaction_types": ["thumbs_up"],
        "note": "Detailed reaction history not available via API"
    }
}
```

### `cross_post_message()`

Cross-post messages between streams.

#### Signature
```python
async def cross_post_message(
    source_message_id: int,
    target_streams: list[str],
    target_topic: str | None = None,
    add_reference: bool = True,
    custom_prefix: str | None = None,
) -> dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`source_message_id`** (int): ID of the original message to cross-post
- **`target_streams`** (list[str]): List of stream names to post to

##### Optional Parameters
- **`target_topic`** (str | None): Topic for cross-posted messages (uses original if None)
- **`add_reference`** (bool): Add reference link to original message (default: True)
- **`custom_prefix`** (str | None): Custom prefix text for cross-posted messages

#### Usage Examples

**Cross-post to multiple streams**:
```python
result = await cross_post_message(
    source_message_id=123456,
    target_streams=["general", "announcements"],
    target_topic="Important Update",
    add_reference=True
)
```

**Cross-post with custom prefix**:
```python
result = await cross_post_message(
    source_message_id=123456,
    target_streams=["team-updates"],
    custom_prefix="FYI from #general:"
)
```

**Cross-post without reference**:
```python
result = await cross_post_message(
    source_message_id=123456,
    target_streams=["archive"],
    add_reference=False
)
```

#### Response Format

```python
{
    "status": "success",
    "source_message_id": 123456,
    "successful_posts": [
        {
            "stream": "general",
            "topic": "Important Update",
            "message_id": 789,
            "status": "success"
        },
        {
            "stream": "announcements",
            "topic": "Important Update",
            "message_id": 790,
            "status": "success"
        }
    ],
    "failed_posts": [],
    "total_attempted": 2,
    "total_successful": 2,
    "total_failed": 0,
    "timestamp": "2024-01-15T10:30:00.000000"
}
```

**Partial success response**:
```python
{
    "status": "success",
    "source_message_id": 123456,
    "successful_posts": [
        {
            "stream": "general",
            "topic": "Updates",
            "message_id": 789,
            "status": "success"
        }
    ],
    "failed_posts": [
        {
            "stream": "private-stream",
            "error": "Not subscribed to stream",
            "status": "error"
        }
    ],
    "total_attempted": 2,
    "total_successful": 1,
    "total_failed": 1,
    "timestamp": "2024-01-15T10:30:00.000000"
}
```

## Identity & Permissions

### Required Capabilities by Function

| Function | User | Bot | Admin | Notes |
|----------|------|-----|-------|-------|
| `message()` | ✅ | ✅ | ✅ | All identities can send messages |
| `search_messages()` | ✅ | ✅ | ✅ | All identities can search |
| `edit_message()` | ✅ Own | ❌ | ✅ All | Users can edit own messages |
| `bulk_operations()` | ✅ Limited | ✅ Limited | ✅ Full | Admin required for delete operations |
| `message_history()` | ✅ | ✅ | ✅ | All identities can view history |
| `cross_post_message()` | ✅ | ✅ | ✅ | Requires write access to target streams |

### Identity-Specific Behavior

**User Identity**:
- Can send messages to subscribed streams
- Can edit own messages within time limit
- Limited bulk operations (no delete)

**Bot Identity**:
- Automated messaging capabilities
- Schedule messages and drafts
- Bulk read/flag operations

**Admin Identity**:
- Full message management
- Can edit/delete any message
- Complete bulk operation access

## Error Handling

### Common Error Responses

All functions return consistent error responses:

```python
{
    "status": "error",
    "error": "Descriptive error message",
    "operation": "operation_name"  # When applicable
}
```

### Common Error Scenarios

- **Missing Required Parameters**: Topic required for stream messages
- **Invalid IDs**: Invalid message ID or stream ID
- **Permission Denied**: Insufficient permissions for operation
- **Not Found**: Stream, message, or user not found
- **API Errors**: Zulip API returned an error

## Best Practices

1. **Handle Errors Gracefully** - Check status field in all responses
2. **Use Appropriate Anchors** - Choose the right anchor for message retrieval
3. **Batch Operations** - Use bulk_operations for multiple message actions
4. **Limit Message Retrieval** - Use reasonable num_before/num_after values
5. **Validate Parameters** - Ensure required parameters are provided
6. **Use Appropriate Identity** - Bot for automation, user for interactive operations

## Implementation Notes

- Message content is automatically truncated at 50KB to prevent issues
- Draft messages are stored locally (not in Zulip)
- Scheduled messages use Zulip's native scheduling API
- Narrow filters support both NarrowFilter objects and dict format
- All timestamps are returned in ISO format
- Message IDs are integers, not strings

---

**Related**: [Streams API](streams.md) | [Events API](events.md) | [Users API](users.md)