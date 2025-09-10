# ZulipChat MCP Server

<div align="center">

**Connect AI assistants to Zulip Chat**

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)

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

## Version 2.0

Complete architectural refactor with modular structure organized into `core/utils/services/tools/integrations` packages. The server now supports dual identity systems, allowing AI agents to operate with dedicated bot credentials instead of user accounts.

### Key Features

- **Dual Identity System**: Separate bot and user credential management
- **Agent Management**: Registration, tracking, and lifecycle management for AI agents
- **Message Operations**: Send, edit, react, and search across all message types
- **Stream Management**: Create, modify, and manage Zulip streams
- **Performance Monitoring**: Built-in health checks and metrics collection
- **Database Integration**: DuckDB for persistent storage and caching

### Available Tools

The server provides 22 MCP tools across four categories:

- **Messaging**: `send_message`, `edit_message`, `add_reaction`, `get_messages`
- **Streams**: `get_streams`, `create_stream`, `subscribe_to_stream`, `get_stream_topics`  
- **Search**: `search_messages`, `get_users`, `get_daily_summary`
- **Agents**: `register_agent`, `send_agent_message`, `get_agent_status`, `list_agents`

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


## Available Tools

Your AI assistant can use these Zulip tools:

### Core Messaging Tools
| Tool | What it does | Example |
|------|--------------|---------|
| `send_message` | Send messages to streams or users | "Post update to #releases" |
| `get_messages` | Retrieve recent messages | "Show me the last 10 messages in #general" |
| `search_messages` | Search across all messages | "Find messages about deployment" |
| `get_streams` | List available streams | "What streams can I access?" |
| `get_users` | List organization users | "Who's in the workspace?" |
| `add_reaction` | Add emoji reactions | "React with 👍 to the last message" |
| `edit_message` | Edit existing messages | "Fix the typo in my last message" |
| `get_daily_summary` | Generate activity reports | "Create a summary of today's activity" |

### Agent Communication Tools (v1.4.0)
| Tool | What it does | Example |
|------|--------------|---------|
| `register_agent` | Register AI agent with auto-detection | "Register Claude Code for this project" |
| `agent_message` | Send project-aware notifications | "Notify completion of task" |
| `request_user_input` | Request input with context | "Ask which branch to deploy" |
| `send_agent_status` | Send status updates | "Update progress to 75%" |
| `start_task` | Start task with tracking | "Begin implementing auth feature" |
| `update_task_progress` | Update task progress | "Mark subtask as complete" |
| `complete_task` | Complete task with summary | "Finish task with test results" |
| `list_instances` | List all active instances | "Show all Claude Code instances" |

### Stream Management Tools
| Tool | What it does | Example |
|------|--------------|---------|
| `create_stream` | Create new streams | "Create stream for project-x" |
| `rename_stream` | Rename existing streams | "Rename stream to archived-project" |
| `archive_stream` | Archive streams | "Archive old project stream" |

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
- **Architecture**: v2.0 modular design with FastMCP framework
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
- `tests/` - Test suite (import paths updated for v2.0)

### Recent Changes
The codebase underwent a complete v2.0 architectural refactor. All import paths have been updated to the new modular structure. Previous versions used flat imports like `from zulipchat_mcp.client import` but v2.0 uses `from src.zulipchat_mcp.core.client import`.

## Use Cases

- **DevOps**: Automate deployment notifications and incident updates
- **Support**: Route customer questions and create ticket summaries
- **Product**: Generate sprint reports and feature request digests
- **Team Leads**: Daily standups and team activity summaries
- **HR**: Onboarding workflows and announcement automation

## Architecture

ZulipChat MCP v2.0 features a clean, production-ready architecture:

### Core Structure
```
src/zulipchat_mcp/
├── core/           # Core business logic (client, exceptions, security, commands)
├── utils/          # Shared utilities (health, logging, metrics, database)
├── services/       # Background services (scheduler)
├── tools/          # MCP tool implementations (messaging, streams, search, agents)
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
- WARP framework integration for AI agent coordination

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