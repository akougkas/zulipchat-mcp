# ZulipChat MCP v0.5.3

> A Model Context Protocol server that transforms AI assistants into Zulip power users.

[![PyPI](https://img.shields.io/pypi/v/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)

---

## What is ZulipChat MCP?

ZulipChat MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that enables AI assistants like **Claude**, **Gemini**, and **Cursor** to interact with [Zulip](https://zulip.com) workspaces. Install with one command, configure with your existing `zuliprc`, and your AI assistant becomes a Zulip superuser.

**Core Value**: Production-ready MCP server that "just works" — install in 30 seconds, configure with existing credentials, integrate seamlessly.

---

## Quick Start

```bash
# Run the setup wizard (recommended)
uvx --from zulipchat-mcp zulipchat-mcp-setup

# Or run directly with your zuliprc
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

### Claude Code Integration

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

### Gemini CLI / Claude Desktop / Cursor

Add to your MCP config file:

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp", "--zulip-config-file", "/path/to/zuliprc"]
    }
  }
}
```

---

## Complete Feature Set

### 67 MCP Tools Across 8 Categories

ZulipChat MCP provides **67 tools** organized into **8 functional categories**, giving AI assistants comprehensive Zulip capabilities:

| Category | Tools | What It Enables |
|----------|-------|-----------------|
| **Messaging** | 16 | Send, edit, schedule, reactions, bulk mark read/unread |
| **Search & Analytics** | 8 | Advanced search, AI-powered insights, daily summaries |
| **Users & Identity** | 14 | User management, fuzzy name resolution, presence, groups |
| **Agent Communication** | 14 | Teleport-chat, register agents, bidirectional messaging, task tracking |
| **Events** | 4 | Real-time event streams, webhooks, long-polling |
| **Streams & Topics** | 4 | Stream info, topic management, cross-stream ops |
| **Files** | 2 | Upload with progress, share, metadata extraction |
| **System & Workflows** | 5 | Server info, command chains, workflow automation |

---

### Messaging (16 tools)

Full message lifecycle management with scheduling and bulk operations.

| Tool | Description |
|------|-------------|
| `send_message` | Send to streams or DMs with smart formatting |
| `edit_message` | Edit content/topic with propagation control |
| `get_message` | Retrieve message by ID |
| `cross_post_message` | Share across streams with attribution |
| `add_reaction` | Add emoji reaction (Unicode, custom, Zulip) |
| `remove_reaction` | Remove emoji reaction |
| `mark_all_as_read` | Mark all messages read |
| `mark_stream_as_read` | Mark stream messages read |
| `mark_topic_as_read` | Mark topic messages read |
| `mark_messages_unread` | Mark messages as unread |
| `star_messages` | Star messages matching criteria |
| `unstar_messages` | Unstar messages |
| `get_scheduled_messages` | List scheduled messages |
| `create_scheduled_message` | Schedule message for later |
| `update_scheduled_message` | Modify scheduled message |
| `delete_scheduled_message` | Cancel scheduled message |

---

### Search & Analytics (8 tools)

AI-powered search with sentiment analysis and engagement metrics.

| Tool | Description |
|------|-------------|
| `search_messages` | Advanced search with fuzzy matching and filters |
| `advanced_search` | Multi-faceted search across messages, users, streams |
| `construct_narrow` | Build Zulip narrow filters programmatically |
| `check_messages_match_narrow` | Validate messages against narrow |
| `get_daily_summary` | Activity summary with engagement stats |
| `analyze_stream_with_llm` | AI insights: trends, sentiment, participation |
| `analyze_team_activity_with_llm` | Cross-stream team analytics |
| `intelligent_report_generator` | Generate standup, weekly, retrospective reports |

---

### Users & Identity (14 tools)

Comprehensive user management with fuzzy name resolution and dual identity support.

| Tool | Description |
|------|-------------|
| `resolve_user` | **NEW** Fuzzy name-to-email resolution ("Jaime" → jaime@org.zulipchat.com) |
| `get_users` | List organization users with filters |
| `get_user_by_id` | Get user by ID |
| `get_user_by_email` | Get user by email |
| `get_own_user` | Current authenticated user info |
| `get_user_status` | User status text and emoji |
| `update_status` | Set your status |
| `get_user_presence` | User online/idle/offline status |
| `get_presence` | All users presence |
| `get_user_groups` | List user groups |
| `get_user_group_members` | Group membership |
| `is_user_group_member` | Check group membership |
| `mute_user` | Mute notifications from user |
| `unmute_user` | Unmute user |

**Dual Identity System**: Switch between user and bot contexts for different operations.

```python
# Reading with user identity, posting with bot identity
switch_identity("bot")  # For automated responses
switch_identity("user") # For searches requiring user permissions
```

---

### Agent Communication (14 tools)

Bidirectional agent-to-user communication with teleport-chat and task tracking.

| Tool | Description |
|------|-------------|
| `teleport_chat` | **NEW** Send message to user/channel with identity-aware routing and fuzzy names |
| `register_agent` | Register agent instance in database |
| `agent_message` | Send bot-authored messages to users |
| `request_user_input` | Request interactive input with options |
| `wait_for_response` | Poll for user responses (timeout handling) |
| `send_agent_status` | Track agent status updates |
| `start_task` | Initialize task with progress tracking |
| `update_task_progress` | Update task percentage and status |
| `complete_task` | Mark task complete with results |
| `list_instances` | List all registered agent instances |
| `poll_agent_events` | Poll unacknowledged events (now receives DMs + streams) |
| `enable_afk_mode` | Enable AFK notifications (configurable hours, auto-return) |
| `disable_afk_mode` | Return to normal notification mode |
| `get_afk_status` | Check current AFK state |

**Teleport-Chat**: Private bot↔user DM back-channel using bot identity. All org-facing messages (channels, DMs to others) use user identity. Supports `wait_for_reply=True` for synchronous conversations.

**AFK Mode**: When enabled, agents can send notifications even when you're away. Auto-returns after configured hours.

---

### Events (4 tools)

Real-time event handling with webhooks and long-polling.

| Tool | Description |
|------|-------------|
| `register_events` | Register for 20+ event types |
| `get_events` | Long-poll events with queue validation |
| `listen_events` | Webhook integration for external systems |
| `deregister_events` | Cleanup event queues |

---

### Streams & Topics (4 tools)

Stream discovery and topic management.

| Tool | Description |
|------|-------------|
| `get_streams` | List streams with subscription filter |
| `get_stream_info` | Stream details with subscribers |
| `get_stream_topics` | Recent topics in a stream |
| `agents_channel_topic_ops` | Topic operations (move, mute) |

---

### Files (2 tools)

Secure file operations with progress tracking.

| Tool | Description |
|------|-------------|
| `upload_file` | Upload with progress, auto-share to stream/topic |
| `manage_files` | List, get, delete, share, download, thumbnails |

---

### System & Workflows (5 tools)

Server info, workflow automation, and command chains.

| Tool | Description |
|------|-------------|
| `server_info` | Server metadata and capabilities |
| `switch_identity` | Switch between user/bot contexts |
| `execute_chain` | Multi-step workflow automation |
| `list_command_types` | Available chain command types |
| `update_message_flags_for_narrow` | Bulk flag updates |

**Command Chains**: Automate multi-step workflows with conditional logic.

```python
execute_chain([
    {"type": "search_messages", "params": {"query": "bug report"}},
    {"type": "conditional_action", "params": {
        "condition": "len(context['results']) > 0",
        "true_action": {"type": "send_message", "params": {...}}
    }}
])
```

---

## Architecture

### Technology Stack

- **[FastMCP](https://github.com/jlowin/fastmcp)** - High-performance MCP server framework
- **[DuckDB](https://duckdb.org)** - Embedded analytics database for persistence
- **[Pydantic](https://pydantic.dev)** - Data validation and serialization
- **[structlog](https://www.structlog.org)** - Structured logging (stderr only for MCP STDIO)
- **Async-first architecture** - Optimized for concurrent operations

### Project Structure

```
src/zulipchat_mcp/
├── core/           # Client, identity, commands, batch processing
├── tools/          # 67 MCP tools across 8 categories
├── utils/          # Logging, database, health, metrics
├── services/       # Background services (scheduler, listener)
├── integrations/   # AI client integrations
└── config.py       # Configuration management
```

### Singleton Configuration

v0.5.0 introduces singleton pattern for ConfigManager, ensuring CLI arguments are respected consistently across all tools.

---

## What's New in v0.5.2

### Added
- **Teleport-Chat**: `teleport_chat` tool for bidirectional agent-human DMs with identity-aware routing
- **Fuzzy User Resolution**: `resolve_user` tool — "text Jaime" just works
- **Always-On Listener**: Message listener starts automatically, receives DMs + all streams
- **AFK Auto-Return**: AFK mode expires after configured hours

### Fixed
- `poll_agent_events` now returns messages (was always empty)
- Listener sees all messages, not just Agents-Channel
- Display vs delivery email mismatch handled correctly

---

## Requirements

- **Python 3.10+**
- **Zulip account** with API access
- **zuliprc file** (download from Zulip: Settings → Account & privacy → API key)
- **Optional**: Bot account for dual identity features

---

## Configuration Options

| Option | Description |
|--------|-------------|
| `--zulip-config-file PATH` | Path to your zuliprc file |
| `--zulip-bot-config-file PATH` | Optional bot zuliprc for dual identity |
| `--unsafe` | Enable administrative tools (use with caution) |
| `--debug` | Enable debug logging (outputs to stderr) |
| `--enable-listener` | Kept for backward compat (listener is now always-on) |

---

## Common Use Cases

| Use Case | Example |
|----------|---------|
| **DevOps** | Automate deployment notifications and incident updates |
| **Support** | Route customer questions, create ticket summaries |
| **Product** | Generate sprint reports and feature request digests |
| **Team Leads** | Daily standups and team activity summaries |
| **HR** | Onboarding workflows and announcement automation |

---

## Links

- **PyPI**: [pypi.org/project/zulipchat-mcp](https://pypi.org/project/zulipchat-mcp/)
- **GitHub**: [github.com/akougkas/zulipchat-mcp](https://github.com/akougkas/zulipchat-mcp)
- **Documentation**: [docs/README.md](docs/README.md)
- **API Reference**: [docs/api-reference/](docs/api-reference/)
- **Issues**: [github.com/akougkas/zulipchat-mcp/issues](https://github.com/akougkas/zulipchat-mcp/issues)
- **Model Context Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Zulip API**: [zulip.com/api](https://zulip.com/api/)

---

## Privacy & Security

- **No data collection**: Server processes locally, no telemetry
- **Zulip API only**: Only communicates with your configured Zulip instance
- **Credential handling**: API keys never logged or transmitted elsewhere
- **Security policy**: See [SECURITY.md](SECURITY.md) for responsible disclosure

---

## License

MIT - See [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built for the Zulip community • <a href="https://github.com/akougkas/zulipchat-mcp">Contribute on GitHub</a></sub>
</div>
