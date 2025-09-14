# Tool Categories Guide

ZulipChat MCP consolidates 24+ legacy tools into 9 organized categories with 43+ total functions. This guide provides a comprehensive overview of each category, their tools, and usage patterns.

## Category Overview

| Category | Tools | Primary Focus | Identity Support |
|----------|-------|---------------|------------------|
| **[Messaging](#messaging-category)** | 8 | Send, edit, search messages | User, Bot, Admin |
| **[Streams](#streams-category)** | 5 | Stream and topic management | User, Bot, Admin |
| **[Events](#events-category)** | 3 | Real-time event handling | User, Bot |
| **[Users](#users-category)** | 3 | User management & identity | User, Admin |
| **[Search](#search-category)** | 3 | Advanced search & analytics | User, Bot, Admin |
| **[Files](#files-category)** | 2 | File upload & management | User, Bot |
| **[Agents](#agents-category)** | 13 | AI agent coordination | Bot, Admin |
| **[Commands](#commands-category)** | 2 | Workflow automation | User, Bot |
| **[System](#system-category)** | 4 | Server info & meta tools | All |


**Total: 43+ consolidated tools** replacing 24+ legacy functions with improved functionality and consistency.

## Messaging Category

**Module**: `tools/messaging_v25.py`  
**Focus**: Comprehensive message operations with scheduling and cross-posting  
**Replaces**: `send_message`, `edit_message`, `get_messages`, `delete_message`, `add_reaction`, `cross_post_message`

### Tools

#### 1. `message()` - Universal Message Operations
```python
await message(
    operation="send|schedule|draft",  # Required
    type="stream|private",            # Required  
    to="recipient",                   # Required
    content="message content",        # Required
    
    # Advanced parameters
    topic="topic name",
    schedule_at=datetime_obj,
    cross_post_streams=["stream1", "stream2"],
    
    # Expert parameters
    disable_notifications=False,
    widget_content=widget_data
)
```

**Operations Supported:**
- `send`: Immediate message delivery
- `schedule`: Schedule for future delivery
- `draft`: Save as draft for later editing

#### 2. `search_messages()` - Message Search & Retrieval
```python
await search_messages(
    narrow=[
        {"operator": "stream", "operand": "general"},
        {"operator": "search", "operand": "python"}
    ],
    limit=100,
    anchor="newest",
    
    # Advanced options
    include_content_analysis=True,
    cache_results=True
)
```

#### 3. `edit_message()` - Message Editing & Topic Management
```python
await edit_message(
    message_id=12345,
    
    # What to edit
    content="new content",
    topic="new topic", 
    stream_id=67890,  # Move to different stream
    
    # Options
    propagate_mode="change_all",  # Topic changes
    send_notification_to_old_thread=True
)
```

#### 4. `bulk_operations()` - Bulk Message Actions
```python
await bulk_operations(
    operation="mark_read|add_reaction|delete|flag",
    narrow=[{"operator": "stream", "operand": "general"}],
    
    # Operation-specific params
    reaction_name="thumbs_up",  # For add_reaction
    flag_name="read"            # For flag operations
)
```

#### 5. `message_history()` - Edit History & Metadata
```python
await message_history(
    message_id=12345,
    include_content_history=True,
    include_edit_metadata=True
)
```

#### 6. `cross_post_message()` - Multi-Stream Sharing
```python
await cross_post_message(
    original_message_id=12345,
    target_streams=["announcements", "general"],
    custom_content="Custom message for cross-post",
    include_original_link=True
)
```

#### 7. `add_reaction()` - Single Message Reactions
```python
await add_reaction(
    message_id=12345,
    emoji_name="thumbs_up",
    emoji_code="👍",
    reaction_type="unicode_emoji"
)
```

#### 8. `remove_reaction()` - Remove Single Message Reactions
```python
await remove_reaction(
    message_id=12345,
    emoji_name="thumbs_up",
    reaction_type="unicode_emoji"
)
```

### Progressive Disclosure Example

```python
# BASIC: Simple send
await message("send", "stream", "general", "Hello!")

# ADVANCED: With topic and scheduling
await message("send", "stream", "general", "Meeting reminder",
              topic="meetings", schedule_at=datetime(2024, 2, 1, 14, 0))

# EXPERT: Full featured with cross-posting
await message("send", "stream", "announcements", "📢 Important Update",
              topic="updates", cross_post_streams=["general", "development"],
              disable_notifications=False, widget_content=survey_data)
```

## Streams Category

**Module**: `tools/streams_v25.py`  
**Focus**: Stream lifecycle management and analytics  
**Replaces**: `create_stream`, `get_streams`, `subscribe_to_stream`, `get_stream_topics`, `delete_topic`

### Tools

#### 1. `manage_streams()` - Stream CRUD Operations
```python
await manage_streams(
    operation="list|create|update|delete|subscribe|unsubscribe",
    
    # For create/update
    stream_names=["new-stream"],
    properties={
        "description": "Stream description",
        "is_private": False,
        "announce": True
    },
    
    # For subscribe/unsubscribe
    user_ids=[123, 456]
)
```

**Operations Supported:**
- `list`: Get accessible streams
- `create`: Create new streams  
- `update`: Modify stream properties
- `delete`: Remove streams
- `subscribe`/`unsubscribe`: Manage subscriptions

#### 2. `manage_topics()` - Topic Operations
```python
await manage_topics(
    stream_id=12345,
    operation="list|move|delete|mark_read|mute|unmute",
    
    # For move operations
    source_topic="old-topic",
    target_topic="new-topic", 
    target_stream_id=67890,
    
    # Options
    propagate_mode="change_all",
    send_notification_to_old_thread=False
)
```

#### 3. `get_stream_info()` - Detailed Stream Information
```python
await get_stream_info(
    stream_name="general",  # Or stream_id=12345
    include_topics=True,
    include_subscribers=True,
    include_settings=True
)
```

#### 4. `stream_analytics()` - Stream Statistics & Insights
```python
await stream_analytics(
    stream_name="general",
    include_user_activity=True,
    include_topic_stats=True,
    time_range_days=30
)
```

**Analytics Provided:**
- Message counts and trends
- User activity patterns  
- Topic distribution
- Peak activity times
- Growth metrics

#### 5. `manage_stream_settings()` - Notification & Permission Settings
```python
await manage_stream_settings(
    stream_id=12345,
    settings={
        "audible_notifications": True,
        "email_notifications": False,
        "push_notifications": True,
        "desktop_notifications": True
    }
)
```

## Events Category

**Module**: `tools/events_v25.py`  
**Focus**: Real-time event streaming and webhooks  
**Replaces**: Legacy agent-based event system

### Tools

#### 1. `register_events()` - Event Queue Registration
```python
await register_events(
    event_types=["message", "reaction", "subscription"],
    narrow=[{"operator": "stream", "operand": "general"}],
    
    # Advanced options
    all_public_streams=False,
    include_subscribers=False,
    fetch_event_types=None  # Auto-detect
)
```

**Supported Event Types:**
- `message`: New messages
- `reaction`: Emoji reactions
- `subscription`: Stream subscriptions
- `realm_user`: User changes
- `presence`: User presence
- `typing`: Typing indicators

#### 2. `get_events()` - Event Polling
```python
await get_events(
    queue_id="queue_123",
    last_event_id=42,
    timeout=60,  # Long polling timeout
    
    # Options
    dont_block=False,
    event_types=["message"]  # Filter events
)
```

#### 3. `listen_events()` - Continuous Event Listening
```python
await listen_events(
    event_types=["message", "reaction"],
    duration=300,  # Listen for 5 minutes
    
    # Webhook support
    callback_url="https://myapp.com/webhook",
    webhook_timeout=30,
    
    # Processing options
    batch_size=10,
    max_queue_size=1000
)
```

**Features:**
- Long-polling support
- Webhook integration
- Automatic queue cleanup
- Event filtering and batching

## Users Category

**Module**: `tools/users_v25.py`  
**Focus**: User management and identity switching  
**Replaces**: `get_users`, `get_user_presence`, `update_user`

### Tools

#### 1. `manage_users()` - User Information & Management
```python
await manage_users(
    operation="list|get|update|presence|groups|avatar|profile_fields",
    
    # User identification
    user_id=123,        # Or email="user@example.com"
    
    # For update operations
    full_name="New Name",
    status_text="Working on project",
    status_emoji=":computer:",
    
    # Options
    include_custom_profile_fields=True,
    client_gravatar=False
)
```

**Operations Supported:**
- `list`: Get all users
- `get`: Get specific user info
- `update`: Update user profile
- `presence`: Update/get presence status
- `groups`: Get user group memberships
- `avatar`: Update user avatar
- `profile_fields`: Manage custom profile fields

#### 2. `switch_identity()` - Dynamic Identity Management
```python
await switch_identity(
    identity_type="user|bot|admin",
    
    # Options
    validate_credentials=True,
    persistent=True,  # vs temporary switch
    
    # For status/info operations
    operation="status|capabilities|switch"
)
```

**Identity Types:**
- `user`: Standard user operations
- `bot`: Automated agent operations
- `admin`: Administrative operations

#### 3. `manage_user_groups()` - User Group Operations
```python
await manage_user_groups(
    operation="create|update|delete|add_members|remove_members",
    
    # Group identification
    group_name="developers",  # Or group_id=123
    
    # Group properties
    description="Development team",
    members=[123, 456, 789],
    
    # For member operations
    user_ids=[101, 102]
)
```

## Search Category

**Module**: `tools/search_v25.py`  
**Focus**: Advanced search with analytics and insights  
**Replaces**: `search_messages`, `get_message_history`

### Tools

#### 1. `advanced_search()` - Enhanced Message Search
```python
await advanced_search(
    query="python OR javascript",
    search_filters=[
        {"operator": "stream", "operand": "development"},
        {"operator": "after", "operand": "2024-01-01"}
    ],
    
    # Advanced options
    include_content_analysis=True,
    sentiment_analysis=True,
    topic_extraction=True,
    cache_results=True,
    cache_ttl=300
)
```

**Features:**
- Natural language queries
- Complex filter combinations
- Content analysis and sentiment
- Result caching for performance

#### 2. `analytics()` - Message Data Analytics
```python
await analytics(
    metric="activity|sentiment|topics|participation",
    narrow=[{"operator": "stream", "operand": "general"}],
    group_by="user|stream|day|hour",

    # Advanced analytics options
    format="summary|chart_data|detailed",
    time_range_days=30
)
```

#### 3. `get_daily_summary()` - Daily Activity Reports
```python
await get_daily_summary(
    hours_back=24,
    target_streams=["general", "announcements"],
    include_stream_details=True,
    include_user_activity=True
)
```

**Analytics Capabilities:**
- Message frequency analysis
- User activity patterns
- Topic trend analysis
- Sentiment distribution
- Time-based patterns
- Daily engagement summaries

## Files Category

**Module**: `tools/files_v25.py`  
**Focus**: File upload and management with metadata  
**Replaces**: `upload_file`, legacy file operations

### Tools

#### 1. `upload_file()` - Advanced File Upload
```python
await upload_file(
    file_data=file_bytes,
    filename="document.pdf",
    
    # Options
    validate_file=True,
    extract_metadata=True,
    progress_callback=progress_handler,
    
    # Advanced options
    expected_hash="sha256:abc123...",
    mime_type_override="application/pdf",
    chunk_size=8192
)
```

**Features:**
- MIME type detection
- File validation and security checks
- Progress tracking for large files
- Metadata extraction
- Hash verification

#### 2. `manage_files()` - File Operations & Metadata
```python
await manage_files(
    operation="list|get|delete|metadata|update",
    
    # File identification
    file_id=12345,
    url="https://uploads.zulipusercontent.net/...",
    
    # For metadata operations
    new_filename="updated-name.pdf",
    description="Updated description",
    
    # Options
    include_metadata=True,
    validate_access=True
)
```

## Agents Category

**Module**: `tools/agents.py`
**Focus**: AI agent coordination and task management
**Identity**: Bot, Admin required for messaging functions

### Tools

#### 1. `register_agent()` - Agent Registration
```python
await register_agent(
    agent_type="claude-code",
    project_dir="/path/to/project",
    session_id="session_123",
    host="hostname"
)
```

#### 2. `agent_message()` - Agent Communication
```python
await agent_message(
    content="Task completed successfully",
    topic_prefix="agents",
    message_type="status|question|result",
    context_data={"task_id": "123"}
)
```

#### 3-5. Task Management
```python
# Start task
task = await start_task("agent_123", "Process Data", "Analyze user reports")

# Update progress
await update_task_progress(task["task_id"], 50, "processing")

# Complete task
await complete_task(task["task_id"], "Results saved", "metrics: 100 processed")
```

#### 6-8. User Interaction
```python
# Request user input
request = await request_user_input(
    "Do you want to continue?",
    agent_id="agent_123",
    choices=["yes", "no"],
    context="Data processing workflow"
)

# Wait for response
response = await wait_for_response(request["request_id"])
```

#### 9-11. AFK Mode Management
```python
# Enable AFK mode for 8 hours
await enable_afk_mode(hours=8, reason="Away for meeting")

# Check status
status = await get_afk_status()

# Disable when back
await disable_afk_mode()
```

#### 12-13. Agent Status & Events
```python
# Send agent status
await send_agent_status("agent_123", "working", "Processing files")

# Poll for events
events = await poll_agent_events(limit=50)
```

## Commands Category

**Module**: `tools/commands.py`
**Focus**: Workflow automation and command chaining
**Replaces**: Legacy workflow tools

### Tools

#### 1. `execute_chain()` - Command Chain Execution
```python
await execute_chain([
    {
        "type": "send_message",
        "params": {
            "message_type": "stream",
            "to": "general",
            "content": "Starting analysis..."
        }
    },
    {
        "type": "search_messages",
        "params": {
            "narrow": [{"operator": "stream", "operand": "general"}],
            "limit": 100
        }
    },
    {
        "type": "conditional_action",
        "condition": "len(context['messages']) > 50",
        "true_action": {
            "type": "send_message",
            "params": {"content": "Found many messages"}
        }
    }
])
```

**Supported Command Types:**
- `send_message`: Send Zulip messages
- `wait_for_response`: Poll for user input
- `search_messages`: Query messages
- `conditional_action`: Branching logic

#### 2. `list_command_types()` - Available Commands
```python
# Returns supported command types for chain building
types = await list_command_types()
# ["send_message", "wait_for_response", "search_messages", "conditional_action"]
```

## System Category

**Module**: `tools/system.py`
**Focus**: Server metadata and development support
**Identity**: All types supported

### Tools

#### 1. `server_info()` - Server Capabilities
```python
info = await server_info()
# Returns: name, version, identities, routing_hints, limitations
```

#### 2. `tool_help()` - Tool Documentation
```python
help = await tool_help("message")
# Returns: comprehensive docstring, examples, parameters
```

#### 3. `identity_policy()` - Identity Guidelines
```python
policy = await identity_policy()
# Returns: when to use USER/BOT/ADMIN identities
```

#### 4. `bootstrap_agent()` - Agent Registration Helper
```python
result = await bootstrap_agent("claude-code")
# Wrapper around agents.register_agent for initialization
```


## Cross-Category Integration

### Common Integration Patterns

#### 1. Message → Stream Analytics
```python
# Send message and analyze stream impact
await message("send", "stream", "general", "Project update")

analytics = await stream_analytics(
    stream_name="general",
    include_recent_activity=True
)
```

#### 2. Events → User Management
```python
# Listen for new users and update groups
queue = await register_events(["realm_user"])

events = await get_events(queue["queue_id"])
for event in events.get("events", []):
    if event["type"] == "realm_user" and event["op"] == "add":
        await manage_user_groups(
            "add_members",
            group_name="new-users", 
            user_ids=[event["person"]["user_id"]]
        )
```

#### 3. Search → File Upload → Messaging
```python
# Search for reports, upload new one, share via message
results = await advanced_search(
    query="monthly report",
    search_filters=[{"operator": "has", "operand": "attachment"}]
)

file_result = await upload_file(file_data, "monthly-report-march.pdf")

await message(
    "send", "stream", "reports",
    f"March report uploaded: [monthly-report-march.pdf]({file_result['url']})",
    topic="monthly-reports"
)
```

## Tool Selection Guidelines

### Choose Messaging When:
- Sending, editing, or searching messages
- Need scheduling or cross-posting
- Bulk message operations required

### Choose Streams When:
- Managing stream lifecycle
- Topic organization and cleanup  
- Need stream analytics and insights

### Choose Events When:
- Real-time event processing
- Building reactive applications
- Need webhook integration

### Choose Users When:
- User information and management
- Identity switching required
- Group membership operations

### Choose Search When:
- Complex search requirements
- Need content analysis
- Require search analytics

### Choose Files When:
- File upload and management
- Need metadata extraction
- Security validation required

### Choose Agents When:
- AI agent coordination needed
- Task tracking and progress reporting
- User interaction during automation
- AFK mode for away scenarios

### Choose Commands When:
- Multi-step workflow automation
- Conditional logic in workflows
- Chain complex operations together

### Choose System When:
- Need server capabilities info
- Debugging tool usage
- Identity management guidance
- Agent initialization



## Performance Considerations

### Caching Strategy by Category

- **Messaging**: Short-term caching (1-5 minutes)
- **Streams**: Medium-term caching (5-15 minutes)
- **Events**: No caching (real-time data)
- **Users**: Long-term caching (10-30 minutes)
- **Search**: Configurable caching (5-60 minutes)
- **Files**: Metadata caching (15-30 minutes)
- **Agents**: Database persistence (permanent)
- **Commands**: Context caching (execution duration)
- **System**: Static data (application lifetime)


### Rate Limiting by Category

Each category has optimized rate limits:
- High-frequency: Events, Messaging, Agents (polling)
- Medium-frequency: Search, Streams, Users, Commands
- Low-frequency: Files, System

### Batch Operation Support

Categories supporting bulk operations:
- ✅ **Messaging**: Bulk mark read, reactions, operations
- ✅ **Streams**: Bulk subscription management
- ❌ **Events**: Individual event processing
- ✅ **Users**: Bulk user operations, group management
- ❌ **Search**: Single query processing
- ❌ **Files**: Individual file operations
- ✅ **Agents**: Batch task operations
- ✅ **Commands**: Chain multiple operations
- ❌ **System**: Individual meta operations  


---

**Next**: [Foundation Components](foundation-components.md) - Deep dive into core infrastructure components