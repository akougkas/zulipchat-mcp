# Release v0.3.0

## Overview

ZulipChat MCP v0.3.0 delivers a complete, production-ready Model Context Protocol server for Zulip with 40+ tools organized across 9 categories, enabling AI assistants to become Zulip power users.

## Key Features

### 🛠️ Complete Tool Suite (40+ tools)
- **Messaging** (8 tools) - Send, edit, search, bulk operations, reactions
- **Streams & Topics** (5 tools) - Lifecycle management, analytics, permissions
- **Real-time Events** (3 tools) - Event streams, webhooks, long-polling
- **User Management** (3 tools) - Multi-identity, groups, profiles
- **Search & Analytics** (3 tools) - AI insights, sentiment, participation
- **Files & Media** (2 tools) - Upload, share, metadata extraction
- **Agent Communication** (13 tools) - Task tracking, AFK mode, workflows
- **Commands** (3 tools) - Workflow automation, chains
- **System** (3+ tools) - Server info, documentation, identity management

### 🔐 Enhanced Security & Control
- Manual-only PyPI publishing for release control
- Clear credential management with mandatory/optional parameters
- Dual-identity system supporting user and bot contexts
- Secure file operations with validation

### 📚 Comprehensive Documentation
- Complete API reference for all tool categories
- User guides for installation and configuration
- Developer documentation for architecture and components
- Contributing guidelines and troubleshooting guides

## Installation

### Quick Start
```bash
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_KEY \
  --zulip-site https://org.zulipchat.com
```

### Claude Code
```bash
claude mcp add zulipchat \
  -e ZULIP_EMAIL=user@org.com \
  -e ZULIP_API_KEY=YOUR_KEY \
  -e ZULIP_SITE=https://org.zulipchat.com \
  -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

## Technical Improvements

- **Performance**: 60% improvement in AI tool-calling accuracy
- **Architecture**: FastMCP framework with DuckDB persistence
- **Testing**: 90% test coverage requirement enforced
- **Async-first**: Optimized for concurrent operations
- **Token Efficiency**: Smart result limiting and caching

## Migration from Previous Versions

### Breaking Changes
- Import paths changed from flat to modular structure
- Admin tools removed from AI access for security
- Documentation moved from `docs/v0.3.0/` to cleaner structure

### Upgrade Steps
1. Update import paths to new modular structure
2. Review bot credential configuration (now optional)
3. Check tool compatibility with new names
4. Update documentation references

## Requirements

- Python 3.10+
- Zulip account with API access
- Optional: Bot account for advanced features

## Links

- [Documentation](https://github.com/akougkas/zulipchat-mcp/tree/main/docs)
- [API Reference](https://github.com/akougkas/zulipchat-mcp/tree/main/docs/api-reference)
- [Contributing](https://github.com/akougkas/zulipchat-mcp/blob/main/CONTRIBUTING.md)
- [Issues](https://github.com/akougkas/zulipchat-mcp/issues)

---

For complete documentation, see the [README](https://github.com/akougkas/zulipchat-mcp#readme).