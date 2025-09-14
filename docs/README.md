# ZulipChat MCP Documentation

A comprehensive Model Context Protocol (MCP) server for Zulip integration with advanced identity management, progressive disclosure, and robust error handling.

## 🚀 Quick Navigation

### For Users
- **[Installation Guide](user-guide/installation.md)** - Get started with ZulipChat MCP
- **[Quick Start](user-guide/quick-start.md)** - Basic usage examples  
- **[Configuration](user-guide/configuration.md)** - Environment setup and credentials

### For Developers
- **[Architecture Overview](developer-guide/architecture.md)** - System design and patterns
- **[Tool Categories](developer-guide/tool-categories.md)** - 9 consolidated tool groups
- **[Foundation Components](developer-guide/foundation-components.md)** - Core infrastructure

### API Reference
| Category | Description | Key Functions |
|----------|-------------|---------------|
| [Messaging](api-reference/messaging.md) | Send, edit, search messages | `message()`, `search_messages()`, `edit_message()` |
| [Streams](api-reference/streams.md) | Stream and topic management | `manage_streams()`, `manage_topics()` |
| [Events](api-reference/events.md) | Real-time event system | `register_events()`, `get_events()`, `listen_events()` |
| [Users](api-reference/users.md) | User management & identity | `manage_users()`, `switch_identity()` |
| [Search](api-reference/search.md) | Advanced search & analytics | `advanced_search()`, `analytics()` |
| [Files](api-reference/files.md) | File upload & management | `upload_file()`, `manage_files()` |
| [Agents](api-reference/agents.md) | AI agent lifecycle & communication | `register_agent()`, `agent_message()`, `request_user_input()` |
| [Commands](api-reference/commands.md) | Workflow automation & chains | `execute_chain()`, `list_command_types()` |
| [System](api-reference/system.md) | Server meta & identity management | `server_info()`, `tool_help()`, `identity_policy()` |


### Migration & Support
- **[Migration Guide](migration-guide.md)** - Migrating from legacy tools
- **[Troubleshooting](troubleshooting.md)** - Error handling and operational support

## 🎯 Key Features

### Multi-Identity Support  
- **User Identity**: Standard user permissions
- **Bot Identity**: Automated agent capabilities  
- **Admin Identity**: Full organizational access
- **Dynamic switching** with context preservation

### Progressive Parameter Disclosure
- **Basic mode**: Essential parameters only
- **Advanced mode**: Extended functionality
- **Expert mode**: Full feature access
- Automatic complexity management

### Robust Error Handling
- **Intelligent retries** with exponential backoff
- **Rate limiting** with token bucket algorithm
- **Circuit breaker** patterns for reliability
- **Comprehensive logging** and metrics

## 🛠 Architecture Highlights

- **Identity-aware operations** with granular permissions
- **Stateless design** for scalability
- **Async/await** for high performance  
- **Comprehensive validation** with sanitization
- **Backward compatibility** with migration framework
- **Health monitoring** and operational metrics

## 🔄 Version Compatibility

- **Current**: v2.5.0 (active development)
- **Legacy tools**: Supported with deprecation warnings
- **Migration timeline**: Legacy removal in v3.0.0  
- **Python support**: 3.10, 3.11, 3.12
- **Zulip API**: v0.9.0+

## 📦 Tool Categories Overview

| Category | Tools | Primary Use Cases |
|----------|-------|-------------------|
| **Messaging** | 6 tools | Send, schedule, edit, cross-post messages |
| **Streams** | 5 tools | Create, manage, analyze streams and topics |
| **Events** | 3 tools | Real-time event handling and webhooks |
| **Users** | 3 tools | User management and identity switching |
| **Search** | 2 tools | Advanced search with analytics |
| **Files** | 2 tools | File upload and management |
| **Agents** | 13 tools | AI agent lifecycle, communication, and task management |
| **Commands** | 2 tools | Workflow automation and command chain execution |
| **System** | 4 tools | Server metadata, tool documentation, identity policies |


**Total**: 40+ tools across 9 categories with comprehensive workflow automation

## 🔗 Integration Examples

```python
# Identity-aware messaging
await message("send", "stream", "general", "Hello world!", 
              topic="greetings")

# Progressive parameter validation  
await manage_streams("create", stream_names=["project-updates"],
                    properties={"description": "Team updates"})

# Real-time event listening
queue = await register_events(["message", "reaction"])
events = await get_events(queue["queue_id"])
```

## 📈 Migration Path

1. **Current state**: Legacy and v2.5.0 tools coexist
2. **Transition phase**: Gradual adoption with compatibility warnings
3. **Target state**: Pure v2.5.0 architecture (v3.0.0)

## 🆘 Getting Help

- **Installation issues**: See [Installation Guide](user-guide/installation.md)
- **Configuration problems**: Check [Configuration](user-guide/configuration.md) 
- **Runtime errors**: Review [Troubleshooting](troubleshooting.md)
- **API questions**: Browse [API Reference](api-reference/)
- **Migration concerns**: Follow [Migration Guide](migration-guide.md)

---

**ZulipChat MCP v2.5.0** - Production-ready MCP server with comprehensive Zulip integration