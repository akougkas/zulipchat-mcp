# ZulipChat MCP Server

<div align="center">

**Connect AI assistants to Zulip Chat**

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Version](https://img.shields.io/badge/Version-2.5.0-green)](https://github.com/akougkas2030/zulipchat-mcp)

[Quick Start](#quick-start) • [Installation](#installation) • [Tools](#available-tools) • [Examples](#examples)

</div>

## What is this?

ZulipChat MCP lets AI assistants like Claude, ChatGPT, and Cursor interact with your Zulip workspace. Send messages, search conversations, create summaries - all through natural language.

### Real Examples

```text
You: "Send a message to #general saying the deployment is complete"
AI: ✓ Message sent to #general

You: "What did people discuss in #engineering today?"
AI: Here's a summary of today's engineering discussions...

You: "Generate a daily summary of all active streams"
AI: Creating your daily digest...
```

## Version 2.5.0

This version marks a significant milestone for `zulipchat-mcp`, focusing on security, robustness, and simplification. The codebase has been streamlined to provide a more maintainable and secure platform for connecting AI assistants to Zulip.

### Key Features

- **Dual Identity System**: Separate bot and user credential management.
- **Secure by Default**: AI-accessible administrative tools have been removed to enhance security.
- **Robust Messaging**: Bulk operations are now powered by an intelligent `BatchProcessor` that handles rate limiting and retries.
- **Simplified Architecture**: The project has been simplified by removing over-engineered and non-essential features.
- **Performance Monitoring**: Built-in health checks and metrics collection.
- **Database Integration**: DuckDB for persistent storage and caching.

## Available Tools (v2.5.0)

The server provides a consolidated and powerful set of tools organized into 6 categories:

### 1. Core Messaging Tools
| Tool | What it does |
|------|--------------|
| `message` | Send, schedule, or draft messages. |
| `search_messages` | Search and retrieve messages with powerful filters. |
| `edit_message` | Edit message content or topic, and move messages. |
| `bulk_operations` | Perform bulk actions like marking messages as read or adding reactions. |
| `message_history` | Get the edit history of a message. |
| `cross_post_message` | Share a message across multiple streams. |
| `add_reaction` / `remove_reaction` | Add or remove a reaction from a single message. |

### 2. Stream & Topic Management
| Tool | What it does |
|------|--------------|
| `manage_streams` | List, create, subscribe to, or update streams. |
| `manage_topics` | Mute, move, or delete topics within a stream. |
| `get_stream_info` | Get detailed information about a stream. |

### 3. Event Streaming
| Tool | What it does |
|------|--------------|
| `register_events` | Subscribe to real-time event streams (e.g., new messages). |
| `get_events` | Poll for events from a registered queue. |
| `listen_events` | Listen for events with callback support. |

### 4. User & Authentication
| Tool | What it does |
|------|--------------|
| `manage_users` | Get user information and manage user settings. |
| `switch_identity` | Switch between user, bot, and admin identities. |
| `manage_user_groups` | Create and manage user groups. |

### 5. Advanced Search & Analytics
| Tool | What it does |
|------|--------------|
| `advanced_search` | Perform multi-faceted searches across messages, users, and streams. |
| `analytics` | Get analytics and insights from message data. |
| `get_daily_summary` | Generate a daily summary of activity. |

### 6. File & Media Management
| Tool | What it does |
|------|--------------|
| `upload_file` | Upload files to Zulip. |
| `manage_files` | List, download, or delete uploaded files. |

## Quick Start

### Claude Code (Current Setup)
```bash
# Clone and setup for development:
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync

# Add to Claude Code:
claude mcp add zulipchat uv run zulipchat-mcp

# Configure credentials in Claude Code when prompted:
# - ZULIP_EMAIL: your-email@domain.com  
# - ZULIP_API_KEY: your-api-key
# - ZULIP_SITE: https://your-org.zulipchat.com
# - ZULIP_BOT_EMAIL: bot-email@domain.com (optional)
# - ZULIP_BOT_API_KEY: bot-api-key (optional)
```

### Standard MCP Installation
```bash
# Install directly with uvx:
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

## Installation

### For Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/akougkas/zulipchat-mcp.git", "zulipchat-mcp"],
      "env": {
        "ZULIP_EMAIL": "bot@your-org.zulipchat.com",
        "ZULIP_API_KEY": "your-api-key",
        "ZULIP_SITE": "https://your-org.zulipchat.com"
      }
    }
  }
}
```

### For Cursor / Continue / Windsurf

Same configuration format - just add to your client's MCP config:

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/akougkas/zulipchat-mcp.git", "zulipchat-mcp"],
      "env": {
        "ZULIP_EMAIL": "bot@your-org.zulipchat.com",
        "ZULIP_API_KEY": "your-api-key",
        "ZULIP_SITE": "https://your-org.zulipchat.com"
      }
    }
  }
}
```

## Resources

Access Zulip data directly:

- `zulip://stream/{name}` - Stream message history
- `zulip://streams` - All available streams
- `zulip://users` - Organization users

## Smart Prompts

Built-in prompts for common tasks:

- `daily_summary` - Comprehensive daily report
- `morning_briefing` - Overnight activity summary  
- `catch_up` - Quick summary of recent messages

## Examples

### Daily Standup Automation
```text
You: "Post our daily standup reminder to #team"
AI: ✓ Posted standup reminder with yesterday's summary
```

### Smart Search
```text
You: "Find all messages from Alice about the API redesign"
AI: Found 12 messages from Alice discussing API redesign...
```

### Activity Reports
```text
You: "Generate a weekly summary for #product"
AI: Here's your weekly product channel summary...
```

### Message Management
```text
You: "Edit my last message to fix the meeting time to 3pm"
AI: ✓ Message updated
```

## Configuration Options

### Environment Variables
```bash
export ZULIP_EMAIL="bot@zulip.com"
export ZULIP_API_KEY="your-key"
export ZULIP_SITE="https://org.zulipchat.com"
```

### Config File
Create `~/.config/zulipchat-mcp/config.json`:
```json
{
  "email": "bot@zulip.com",
  "api_key": "your-key",
  "site": "https://org.zulipchat.com"
}
```

### Direct in MCP Client
Pass credentials directly in your MCP client configuration (see installation section).

## Development

### Local Setup
```bash
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync
uv run zulipchat-mcp
```

### Testing Connection
```bash
uv run python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
print(f'Connected! Identity: {client.identity_name}')
"
```

## Troubleshooting

**"No Zulip email found"**
- Set the environment variables shown in Quick Start
- Or create a config file in `~/.config/zulipchat-mcp/config.json`

**"Connection failed"**
- Verify your API key is correct
- Check your Zulip site URL includes `https://`
- Ensure your bot has permissions for the streams

**"Module not found"**
- Update uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Reinstall: `uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp`

## For AI Agents

If you're an AI agent analyzing this repository:

### Repository Structure
- **Language**: Python 3.10+
- **Package Manager**: UV (not pip)
- **Architecture**: v2.5 modular design with FastMCP framework
- **Database**: DuckDB for persistence
- **Testing**: pytest with comprehensive coverage
- **Entry Point**: `src/zulipchat_mcp/server.py`

### Development Commands
```bash
# Setup environment
uv sync

# Run server
uv run zulipchat-mcp

# Run tests  
uv run pytest

# Check imports
uv run python -c "from src.zulipchat_mcp.server import mcp; print('OK')"
```

### Key Implementation Files
- `src/zulipchat_mcp/tools/` - MCP tool implementations
- `src/zulipchat_mcp/core/client.py` - Zulip API wrapper with dual identity
- `src/zulipchat_mcp/core/commands/` - Command chain system
- `src/zulipchat_mcp/config.py` - Configuration management
- `tests/` - Test suite (import paths updated for v2.5)

### Recent Changes
The codebase underwent a complete v2.5 architectural refactor. All import paths have been updated to the new modular structure. Previous versions used flat imports like `from zulipchat_mcp.client import` but v2.5 uses `from src.zulipchat_mcp.core.client import`.

## Use Cases

- **DevOps**: Automate deployment notifications and incident updates
- **Support**: Route customer questions and create ticket summaries
- **Product**: Generate sprint reports and feature request digests
- **Team Leads**: Daily standups and team activity summaries
- **HR**: Onboarding workflows and announcement automation

## Architecture

ZulipChat MCP v2.5 features a clean, production-ready architecture:

### Core Structure
```
src/zulipchat_mcp/
├── core/           # Core business logic (client, exceptions, security, commands)
├── utils/          # Shared utilities (health, logging, metrics, database)
├── services/       # Background services (scheduler)
├── tools/          # MCP tool implementations (messaging, streams, search, events, users, files)
├── integrations/   # AI client integrations (Claude Code, Cursor, etc.)
└── config.py       # Configuration management
```

### Technology Stack
- [FastMCP](https://github.com/jlowin/fastmcp) - High-performance MCP server framework
- [DuckDB](https://duckdb.org) - Embedded analytics database for persistence
- [Pydantic](https://pydantic.dev) - Data validation and serialization
- [UV](https://docs.astral.sh/uv/) - Ultra-fast Python package management
- Async-first architecture for optimal performance
- Smart caching with automatic invalidation
- Comprehensive error handling and monitoring

## Contributing

We welcome contributions! To get started:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

See [AGENTS.md](AGENTS.md) for development guidelines.

## License

MIT - See [LICENSE](LICENSE) for details.

## Links

- [Zulip API Documentation](https://zulip.com/api/)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Report Issues](https://github.com/akougkas/zulipchat-mcp/issues)

---

<div align="center">
  <sub>Built with ❤️ for the Zulip community</sub>
</div>
