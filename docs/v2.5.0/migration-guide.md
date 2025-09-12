# Migration Guide

Complete guide for migrating from legacy ZulipChat MCP tools to v2.5.0 consolidated architecture. This guide covers tool mappings, parameter transformations, and **required manual migration steps**.

> ⚠️ **IMPORTANT**: Legacy tool names are NOT callable through MCP. You MUST update all tool calls to use v2.5.0 names. There is NO automatic backward compatibility for MCP clients.

## Migration Overview

ZulipChat MCP v2.5.0 consolidates legacy tools into 7 organized categories with 23 total functions. While migration mappings exist in the codebase for reference, **legacy tools are NOT registered with the MCP server and cannot be called**.

### Breaking Changes in v2.5.0
- **All legacy tool names are removed from MCP**
- **Manual migration is REQUIRED for all clients**
- **No automatic fallback or compatibility layer**
- **Parameter names and structures have changed**

### Migration Benefits
- **Simplified API**: Fewer tools with consistent patterns
- **Enhanced functionality**: Progressive disclosure and identity management
- **Better performance**: Optimized for modern usage patterns
- **Improved reliability**: Centralized error handling and validation

## Legacy → v2.5.0 Tool Mapping

### Messaging Tools Migration

| Legacy Tool | v2.5.0 Tool | Migration Required | Breaking Changes |
|-------------|-------------|-------------------|------------------|
| `send_message` | [`message()`](api-reference/messaging.md#message) | ❌ MANUAL | Tool name and parameters changed |
| `edit_message` | [`edit_message()`](api-reference/messaging.md#edit_message) | ❌ MANUAL | Different function signature |
| `get_messages` | [`search_messages()`](api-reference/messaging.md#search_messages) | ❌ MANUAL | Complete redesign with narrow filters |
| `delete_message` | [`bulk_operations()`](api-reference/messaging.md#bulk_operations) | ❌ MANUAL | Now part of bulk operations |
| `add_reaction` | [`bulk_operations()`](api-reference/messaging.md#bulk_operations) | ❌ MANUAL | Merged into bulk operations |

#### `send_message` Migration
```python
# ❌ Legacy approach - WILL NOT WORK
# This will fail with "tool not found" error
await mcp.call_tool("send_message", {
    "message_type": "stream",
    "stream": "general", 
    "subject": "topic",
    "content": "Hello world!"
})

# ✅ v2.5.0 approach - REQUIRED
await mcp.call_tool("message", {
    "operation": "send",       # NEW: operation parameter
    "type": "stream",          # RENAMED: message_type → type  
    "to": "general",           # RENAMED: stream → to
    "topic": "topic",          # RENAMED: subject → topic
    "content": "Hello world!"
})
```

#### `get_messages` Migration
```python
# ❌ Legacy approach - WILL NOT WORK
await mcp.call_tool("get_messages", {
    "stream_name": "general",
    "hours_back": 24,
    "limit": 50
})

# ✅ v2.5.0 approach - REQUIRED
from datetime import datetime, timedelta

await mcp.call_tool("search_messages", {
    "narrow": [
        {"operator": "stream", "operand": "general"},
        {"operator": "after", "operand": (datetime.now() - timedelta(hours=24)).isoformat()}
    ],
    "limit": 50
})
```

### Streams Tools Migration

| Legacy Tool | v2.5.0 Tool | Migration Required | Breaking Changes |
|-------------|-------------|-------------------|------------------|
| `create_stream` | [`manage_streams()`](api-reference/streams.md#manage_streams) | ❌ MANUAL | Single → list parameter |
| `get_streams` | [`manage_streams()`](api-reference/streams.md#manage_streams) | ❌ MANUAL | Different operation structure |
| `rename_stream` | [`manage_streams()`](api-reference/streams.md#manage_streams) | ❌ MANUAL | Unified into manage_streams |
| `archive_stream` | [`manage_streams()`](api-reference/streams.md#manage_streams) | ❌ MANUAL | Now a delete operation |
| `get_stream_topics` | [`get_stream_info()`](api-reference/streams.md#get_stream_info) | ❌ MANUAL | New tool name and structure |

#### `create_stream` Migration
```python
# ❌ Legacy approach - WILL NOT WORK
await mcp.call_tool("create_stream", {
    "stream_name": "project-alpha",
    "description": "Alpha project discussion",
    "private": False
})

# ✅ v2.5.0 approach - REQUIRED
await mcp.call_tool("manage_streams", {
    "operation": "create",
    "stream_names": ["project-alpha"],  # NOW: list of names
    "properties": {
        "description": "Alpha project discussion",
        "is_private": False             # RENAMED: private → is_private
    }
)
```

### Events Tools Migration

| Legacy Tool | v2.5.0 Tool | Status | Breaking Changes |
|-------------|-------------|--------|------------------|
| `register_agent` | [`register_events()`](api-reference/events.md#register_events) | ⚠️ Architecture changed | Stateless event queues |
| `poll_agent_events` | [`get_events()`](api-reference/events.md#get_events) | ⚠️ Architecture changed | Queue-based polling |
| `enable_afk_mode` | [`listen_events()`](api-reference/events.md#listen_events) | ⚠️ Architecture changed | Continuous listening |

#### Agent System → Event System Migration
```python
# Legacy agent approach
await register_agent("message_handler", ["message"])
await enable_afk_mode(duration=300)

while True:
    events = await poll_agent_events()
    for event in events:
        await handle_event(event)

# v2.5.0 event approach (manual migration required)
# Option 1: Manual polling
queue = await register_events(["message"])
last_event_id = queue["last_event_id"]

while True:
    events = await get_events(queue["queue_id"], last_event_id)
    for event in events.get("events", []):
        await handle_event(event)
        last_event_id = event["id"]

# Option 2: Automated listening
await listen_events(
    event_types=["message"],
    duration=300,
    callback_url="https://myapp.com/webhook"
)
```

### Users Tools Migration

| Legacy Tool | v2.5.0 Tool | Status | Breaking Changes |
|-------------|-------------|--------|------------------|
| `get_users` | [`manage_users()`](api-reference/users.md#manage_users) | ✅ Auto-migrated | Enhanced user data |
| `get_user_presence` | [`manage_users()`](api-reference/users.md#manage_users) | ✅ Auto-migrated | Unified operation |
| `update_user` | [`manage_users()`](api-reference/users.md#manage_users) | ⚠️ Permissions changed | Admin required for others |

#### User Management Migration
```python
# Legacy approach
users = await get_users()
presence = await get_user_presence(user_id=123)

# v2.5.0 approach (auto-migrated)
users = await manage_users("list")
presence = await manage_users("presence", user_id=123)
```

### Search Tools Migration

| Legacy Tool | v2.5.0 Tool | Status | Breaking Changes |
|-------------|-------------|--------|------------------|
| `search_messages` | [`advanced_search()`](api-reference/search.md#advanced_search) | ✅ Enhanced | More powerful search |
| `get_message_history` | [`analytics()`](api-reference/search.md#analytics) | ⚠️ Manual migration | Now analytics-focused |

### Files & Admin Tools

Files and admin tools are **new in v2.5.0** - no legacy equivalents exist.

## Parameter Transformation Guide

### Common Parameter Changes

#### Naming Conventions
- `message_type` → `type`
- `stream` → `to` (for messaging)
- `subject` → `topic`
- `private` → `is_private`
- `stream_name` → `stream_names` (now accepts lists)

#### New Required Parameters
- **`operation`**: All consolidated tools now require an operation parameter
- **`validation_mode`**: Controls progressive disclosure (defaults to BASIC)

#### New Optional Parameters
- **`identity_override`**: Override identity for specific operations
- **`cache_results`**: Enable result caching for performance
- **`include_metadata`**: Include extended metadata in responses

### Complex Transformations

#### Search Filters (get_messages → search_messages)
```python
# Legacy parameters
{
    "stream_name": "general",
    "hours_back": 24,
    "sender": "alice@example.com",
    "has_attachment": True
}

# v2.5.0 narrow filters
{
    "narrow": [
        {"operator": "stream", "operand": "general"},
        {"operator": "after", "operand": "2024-01-01T00:00:00Z"},
        {"operator": "sender", "operand": "alice@example.com"},
        {"operator": "has", "operand": "attachment"}
    ]
}
```

#### Stream Properties
```python
# Legacy properties
{
    "stream_name": "project-alpha",
    "description": "Project discussion",
    "private": False,
    "invite_only": False
}

# v2.5.0 properties
{
    "stream_names": ["project-alpha"],  # Now a list
    "properties": {
        "description": "Project discussion",
        "is_private": False,           # Renamed
        "invite_only": False
    }
}
```

## Migration Strategies

### Strategy 1: Gradual Migration (Recommended)

1. **Phase 1**: Continue using legacy tools with deprecation warnings
2. **Phase 2**: Migrate high-traffic operations to v2.5.0 tools
3. **Phase 3**: Replace remaining legacy calls before v3.0.0
4. **Phase 4**: Adopt advanced features (progressive disclosure, analytics)

### Strategy 2: Immediate Migration

1. **Identify all legacy tool usage** in codebase
2. **Create mapping table** for your specific use cases
3. **Update function calls** systematically
4. **Test thoroughly** with new parameter formats
5. **Deploy and monitor** for issues

### Strategy 3: Hybrid Approach

1. **Use automated migration** for simple cases
2. **Manual migration** for complex transformations
3. **Gradual adoption** of new features
4. **Performance optimization** using new capabilities

## Migration Tools & Helpers

### Automatic Migration Detection
The system automatically detects and migrates many legacy tool calls:

```python
# Legacy call (automatically migrated)
result = await send_message("stream", "general", "Hello", topic="greetings")

# Equivalent v2.5.0 call (what gets executed)
result = await message("send", "stream", "general", "Hello", topic="greetings")
```

### Migration Checker Tool
```python
async def check_migration_status():
    """Check which tools need manual migration."""
    
    migration_status = {}
    
    # Check for usage of tools requiring manual migration
    manual_migration_tools = [
        "get_messages",
        "delete_message", 
        "delete_topic",
        "register_agent",
        "poll_agent_events"
    ]
    
    for tool in manual_migration_tools:
        usage_count = await count_tool_usage(tool)
        if usage_count > 0:
            migration_status[tool] = {
                "usage_count": usage_count,
                "migration_required": True,
                "new_tool": get_migration_target(tool)
            }
    
    return migration_status
```

### Code Migration Helper
```python
def migrate_legacy_call(legacy_tool: str, legacy_params: dict) -> tuple:
    """Helper to convert legacy tool calls to v2.5.0 format."""
    
    migration_map = {
        "send_message": {
            "new_tool": "message",
            "new_params": {"operation": "send"},
            "param_mapping": {
                "message_type": "type",
                "stream": "to",
                "subject": "topic"
            }
        },
        "get_messages": {
            "new_tool": "search_messages", 
            "param_transformation": transform_get_messages_params
        }
        # ... more mappings
    }
    
    migration = migration_map.get(legacy_tool)
    if not migration:
        raise ValueError(f"No migration available for {legacy_tool}")
    
    return apply_migration(migration, legacy_params)
```

## Testing Your Migration

### Migration Test Suite
```python
async def test_migration_equivalence():
    """Test that migrated calls produce equivalent results."""
    
    test_cases = [
        {
            "legacy_call": ("send_message", {
                "message_type": "stream",
                "stream": "test",
                "content": "test message"
            }),
            "expected_v25_call": ("message", {
                "operation": "send",
                "type": "stream", 
                "to": "test",
                "content": "test message"
            })
        }
    ]
    
    for test_case in test_cases:
        legacy_result = await call_legacy_tool(*test_case["legacy_call"])
        v25_result = await call_v25_tool(*test_case["expected_v25_call"])
        
        assert_equivalent_results(legacy_result, v25_result)
```

### Performance Comparison
```python
async def compare_performance():
    """Compare performance between legacy and v2.5.0 tools."""
    
    import time
    
    # Test legacy performance
    start_time = time.time()
    await get_messages(stream_name="general", limit=100)
    legacy_time = time.time() - start_time
    
    # Test v2.5.0 performance
    start_time = time.time()
    await search_messages(
        narrow=[{"operator": "stream", "operand": "general"}],
        limit=100,
        cache_results=True
    )
    v25_time = time.time() - start_time
    
    return {
        "legacy_time": legacy_time,
        "v25_time": v25_time,
        "improvement": (legacy_time - v25_time) / legacy_time * 100
    }
```

## Common Migration Issues

### Issue 1: Parameter Validation Errors
```python
# Problem: Old parameter names not recognized
await message("send", "stream", "general", "Hello", subject="topic")  # ❌

# Solution: Use new parameter names
await message("send", "stream", "general", "Hello", topic="topic")    # ✅
```

### Issue 2: Identity Permission Errors  
```python
# Problem: New permission requirements
await manage_users("update", user_id=456, full_name="New Name")  # ❌ May fail

# Solution: Use appropriate identity
await switch_identity("admin")
await manage_users("update", user_id=456, full_name="New Name")  # ✅
```

### Issue 3: Event System Architecture Changes
```python
# Problem: Old agent system no longer works
await register_agent("handler", ["message"])  # ❌ Deprecated

# Solution: Use new event system
queue = await register_events(["message"])    # ✅
events = await get_events(queue["queue_id"])
```

### Issue 4: Search Syntax Changes
```python
# Problem: Old search parameters don't translate
await get_messages(stream_name="general", hours_back=24)  # ❌

# Solution: Use narrow syntax
await search_messages(
    narrow=[
        {"operator": "stream", "operand": "general"},
        {"operator": "after", "operand": (datetime.now() - timedelta(hours=24)).isoformat()}
    ]
)  # ✅
```

## Best Practices for Migration

### 1. Start with High-Impact Tools
Prioritize migration of frequently used tools:
- `send_message` → `message()`
- `get_streams` → `manage_streams()`
- `get_users` → `manage_users()`

### 2. Use Progressive Disclosure
Start with basic mode, add complexity gradually:
```python
# Start simple
await message("send", "stream", "general", "Hello")

# Add features as needed
await message(
    "send", "stream", "general", "Important update",
    topic="announcements",
    cross_post_streams=["team-updates"]
)
```

### 3. Leverage New Features
Take advantage of v2.5.0 improvements:
- **Caching**: Enable `cache_results=True` for repeated operations
- **Analytics**: Use `analytics()` for insights
- **Identity switching**: Use `switch_identity()` for appropriate permissions
- **Bulk operations**: Use `bulk_operations()` for efficiency

### 4. Plan for Error Handling
v2.5.0 has enhanced error handling:
```python
try:
    result = await message("send", "stream", "general", "Hello")
    if result["status"] == "error":
        # Handle specific error types
        if result["error_type"] == "RateLimitError":
            await asyncio.sleep(result.get("retry_after", 60))
            # Retry logic
except Exception as e:
    # Enhanced error information available
    logger.error(f"Message send failed: {e}")
```

### 5. Monitor Migration Progress
Track your migration progress:
```python
async def migration_dashboard():
    """Dashboard showing migration progress."""
    
    legacy_usage = await count_legacy_tool_usage()
    v25_usage = await count_v25_tool_usage()
    
    migration_percentage = (v25_usage / (legacy_usage + v25_usage)) * 100
    
    return {
        "migration_percentage": migration_percentage,
        "legacy_calls_remaining": legacy_usage,
        "v25_calls": v25_usage,
        "estimated_completion": calculate_completion_date(migration_percentage)
    }
```

## Migration Checklist

### Pre-Migration
- [ ] Audit current tool usage
- [ ] Identify tools requiring manual migration
- [ ] Plan migration timeline
- [ ] Set up test environment
- [ ] Create backup of current implementation

### During Migration
- [ ] Migrate tools in order of priority
- [ ] Test each migration thoroughly
- [ ] Monitor performance changes
- [ ] Handle deprecation warnings
- [ ] Update documentation and comments

### Post-Migration
- [ ] Verify all legacy tools removed
- [ ] Optimize using new features
- [ ] Update team training materials
- [ ] Monitor system performance
- [ ] Plan for v3.0.0 preparedness

## Support Resources

### Getting Help
- **Documentation**: Comprehensive API reference available
- **Migration issues**: Check troubleshooting guide
- **Community support**: GitHub issues and discussions
- **Professional support**: Available for enterprise customers

### Tools & Utilities
- **Migration checker**: Automated tool usage analysis
- **Parameter converter**: Helper for complex transformations  
- **Test suite**: Validation tools for migration accuracy
- **Performance profiler**: Before/after performance comparison

---

The migration to ZulipChat MCP v2.5.0 provides significant benefits in functionality, performance, and maintainability. With proper planning and the tools provided, migration can be completed smoothly and efficiently.

**Next**: [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions