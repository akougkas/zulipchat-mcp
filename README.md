# ZulipChat MCP Server

<div align="center">

  <h3>Connect your AI assistant to Zulip with 8 powerful tool categories via MCP</h3>

  [![PyPI](https://img.shields.io/pypi/v/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![Downloads](https://img.shields.io/pypi/dm/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![GitHub stars](https://img.shields.io/github/stars/akougkas/zulipchat-mcp)](https://github.com/akougkas/zulipchat-mcp/stargazers)
  [![Last commit](https://img.shields.io/github/last-commit/akougkas/zulipchat-mcp)](https://github.com/akougkas/zulipchat-mcp/commits/main)
  [![Python](https://img.shields.io/pypi/pyversions/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![License](https://img.shields.io/github/license/akougkas/zulipchat-mcp)](LICENSE)
  [![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)

  [🚀 Quick Start](#-quick-start) • [📦 Installation](#-installation) • [📚 Features](#-what-can-you-do) • [🛠️ Tools](#-available-tools) • [💡 Examples](#-real-world-examples) • [📖 Releases](#-releases) • [🤝 Contributing](CONTRIBUTING.md)
</div>

---

## Quick Start

Get your AI assistant connected to Zulip in **30 seconds**:

```bash
# Run setup wizard (recommended)
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

Or manually with a zuliprc file:
```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## What Can You Do?

Your AI assistant becomes a **Zulip superuser**, capable of:

- **Intelligent Messaging** - Send, schedule, search, and manage messages with context awareness
- **Stream Management** - Create, configure, and analyze streams with engagement metrics
- **Real-time Monitoring** - React to events, track activity, and automate responses
- **Advanced Analytics** - Generate insights, sentiment analysis, and participation reports
- **File Operations** - Upload, share, and manage files with automatic distribution
- **Workflow Automation** - Chain complex operations with conditional logic

## Available Tools

<div align="center">

| Category | Tools | Key Capabilities |
|----------|-------|------------------|
| **📨 Messaging** | <details><summary>**8**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `message` \| Send, schedule, or draft messages with **smart formatting** and **delivery options** \|<br>\| `search_messages` \| **Token-limited results** with **narrow filters** and **advanced queries** \|<br>\| `edit_message` \| Edit content + topics with **propagation modes** and **notification control** \|<br>\| `bulk_operations` \| **Progress tracking** for bulk actions across multiple messages \|<br>\| `message_history` \| Complete **audit trail** with **edit timestamps** and **revision tracking** \|<br>\| `cross_post_message` \| **Attribution-aware** sharing across streams with **context preservation** \|<br>\| `add_reaction` \| **Emoji type support** (Unicode, custom, Zulip extra) \|<br>\| `remove_reaction` \| **Emoji type support** (Unicode, custom, Zulip extra) \|<br><br></details> | Send, edit, search, bulk operations, reactions |
| **📁 Streams & Topics** | <details><summary>**5**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `manage_streams` \| **Lifecycle management** with permissions, **bulk subscriptions** \|<br>\| `manage_topics` \| **Cross-stream transfers** with **propagation modes** and notifications \|<br>\| `get_stream_info` \| **Comprehensive details** with subscriber lists and topic inclusion \|<br>\| `stream_analytics` \| **NEW!** Growth trends, engagement metrics, subscriber activity \|<br>\| `manage_stream_settings` \| **NEW!** Notification preferences, appearance, permissions \|<br><br></details> | Lifecycle management, analytics, permissions |
| **⚡ Real-time Events** | <details><summary>**3**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `register_events` \| **20+ event types** with **auto-cleanup** and **queue management** \|<br>\| `get_events` \| **Long-polling support** with **queue validation** and error handling \|<br>\| `listen_events` \| **NEW!** Webhook integration, event filtering, stateless operation \|<br><br></details> | Event streams, webhooks, long-polling |
| **👥 User Management** | <details><summary>**3**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `manage_users` \| **Multi-identity support** (user/bot/admin contexts) \|<br>\| `switch_identity` \| **NEW!** Session continuity with validation and capability tracking \|<br>\| `manage_user_groups` \| **NEW!** Complete group lifecycle with membership management \|<br><br></details> | Multi-identity, groups, profiles |
| **🔍 Search & Analytics** | <details><summary>**3**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `advanced_search` \| **NEW!** Multi-faceted search with **intelligent ranking** and **aggregation** \|<br>\| `analytics` \| **NEW!** AI-powered insights with **sentiment analysis** and **participation metrics** \|<br>\| `get_daily_summary` \| **NEW!** Comprehensive activity summaries with **stream engagement** \|<br><br></details> | AI insights, sentiment, participation |
| **📎 Files & Media** | <details><summary>**2**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `upload_file` \| **NEW!** Progress tracking, **auto-sharing**, **security validation** \|<br>\| `manage_files` \| **NEW!** Complete file lifecycle with **metadata extraction** \|<br><br></details> | Upload, share, metadata extraction |
| **🤖 Agent Communication** | <details><summary>**13**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `register_agent` \| **NEW!** Database persistence with **session tracking** \|<br>\| `agent_message` \| **NEW!** BOT identity messaging with **AFK gating** \|<br>\| `request_user_input` \| **NEW!** Interactive workflows with **intelligent routing** \|<br>\| `start_task` \| **NEW!** Full task lifecycle management \|<br>\| `update_progress` \| **NEW!** Full task lifecycle management \|<br>\| `complete_task` \| **NEW!** Full task lifecycle management \|<br>\| `enable_afk_mode` \| **NEW!** Away-mode automation \|<br>\| `disable_afk_mode` \| **NEW!** Away-mode automation \|<br>\| *...and 5 more tools* \| Advanced workflow automation and monitoring \|<br><br></details> | Task tracking, AFK mode, workflows |
| **⚙️ System & Workflow** | <details><summary>**6+**</summary><br><br>\| **Tool** \| **Capabilities** \|<br>\|-------\|----------------\|<br>\| `server_info` \| **NEW!** Comprehensive metadata with **routing hints** \|<br>\| `tool_help` \| **NEW!** On-demand documentation with **module search** \|<br>\| `execute_chain` \| **NEW!** Sophisticated workflow automation with **branching logic** \|<br>\| *...and 3+ more tools* \| Identity policy, agent bootstrapping, command types \|<br><br></details> | Chains, documentation, server info |

</div>

## 📦 Installation & Setup

### Option 1: Setup Wizard (Recommended)

```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

The wizard will find your zuliprc files, validate credentials, and generate config for your MCP client.

### Option 2: Claude Code

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

Or with dual identity (user + bot):
```bash
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

### Option 3: Gemini CLI / Claude Desktop / Cursor

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

**Dual Identity (User + Bot):**
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-config-file", "/path/to/user/zuliprc",
        "--zulip-bot-config-file", "/path/to/bot/zuliprc"
      ]
    }
  }
}
```

### Getting Your zuliprc

Download from Zulip: **Settings** → **Personal settings** → **Account & privacy** → **API key**

## ⚙️ Configuration Guide

### Authentication (Zuliprc)
The server now strictly requires `zuliprc` files for authentication. This improves security by avoiding plain-text API keys in command arguments.

*   `--zulip-config-file PATH`: Path to your primary User `zuliprc`.
*   `--zulip-bot-config-file PATH`: (Optional) Path to a Bot `zuliprc` for dual identity features.

### Safety Modes
*   **Safe Mode (Default):** Restricts dangerous actions like deleting users or streams.
*   **Unsafe Mode (`--unsafe`):** Enables administrative tools. Use with caution.

### Debugging
*   `--debug`: Enables detailed logging to stderr.

## Documentation

### For Users
- [Installation Guide](docs/user-guide/installation.md) - Step-by-step setup instructions
- [Quick Start Tutorial](docs/user-guide/quick-start.md) - Get running in minutes
- [Configuration Reference](docs/user-guide/configuration.md) - All configuration options
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions

### For Developers
- [Architecture Overview](docs/developer-guide/architecture.md) - System design and components
- [Tool Categories](docs/developer-guide/tool-categories.md) - Tool organization and patterns
- [Foundation Components](docs/developer-guide/foundation-components.md) - Core building blocks
- [Testing Guide](docs/testing/README.md) - Testing strategies and coverage

### API Reference
- [Messaging Tools](docs/api-reference/messaging.md) - Message operations documentation
- [Stream Tools](docs/api-reference/streams.md) - Stream management APIs
- [Event Tools](docs/api-reference/events.md) - Real-time event handling
- [User Tools](docs/api-reference/users.md) - User and identity management
- [Search Tools](docs/api-reference/search.md) - Search and analytics APIs
- [File Tools](docs/api-reference/files.md) - File operations reference

## Additional Resources

### MCP Resources
Access Zulip data directly in your AI assistant:
- `zulip://stream/{name}` - Stream message history
- `zulip://streams` - All available streams
- `zulip://users` - Organization users

### Smart Prompts
Built-in prompts for common tasks:
- `daily_summary` - Comprehensive daily report
- `morning_briefing` - Overnight activity summary
- `catch_up` - Quick summary of recent messages

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

## Common Use Cases

- **DevOps**: Automate deployment notifications and incident updates
- **Support**: Route customer questions and create ticket summaries
- **Product**: Generate sprint reports and feature request digests
- **Team Leads**: Daily standups and team activity summaries
- **HR**: Onboarding workflows and announcement automation


## 🤝 Contributing

We welcome contributions from everyone! Whether you're fixing bugs, adding features, or improving docs.

📖 See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete guide.

<details>
<summary><b>🔧 Development</b> - For contributors</summary>

## Development

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager (required - we use uv exclusively)

### Local Setup
```bash
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync

# Run locally with zuliprc
uv run zulipchat-mcp --zulip-config-file ~/.zuliprc
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

### Quality Checks
```bash
# Run before pushing
uv run pytest -q                  # Tests (85% coverage required)
uv run ruff check .               # Linting
uv run black .                    # Formatting
uv run mypy src                   # Type checking

# Optional security checks
uv run bandit -q -r src
uv run safety check
```

</details>

<details>
<summary><b>🏗️ Architecture</b> - Technical details</summary>

## Architecture

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

</details>

For AI coding agents:
- [AGENTS.md](AGENTS.md) - Repository guidelines and commands
- [CLAUDE.md](CLAUDE.md) - Claude Code specific instructions

## Privacy Policy

This MCP server is designed with privacy as a core principle:

- **No data collection**: This server does not collect, store, or transmit any user data to third parties
- **Local execution**: All processing happens locally on your machine
- **Zulip API only**: The server only communicates with your configured Zulip instance using your provided credentials
- **No telemetry**: No analytics, tracking, or usage data is collected
- **Credential handling**: API keys and credentials are only used to authenticate with your Zulip server and are never logged or transmitted elsewhere

For the full privacy policy, see [PRIVACY.md](PRIVACY.md).

## License

MIT - See [LICENSE](LICENSE) for details.

<!-- mcp-name: io.github.akougkas/zulipchat -->

## Links

- [Zulip API Documentation](https://zulip.com/api/)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Report Issues](https://github.com/akougkas/zulipchat-mcp/issues)

## Community

### Code of Conduct
We're committed to providing a welcoming and inclusive experience for everyone. We expect all participants to:
- Be respectful and collaborative
- Assume positive intent
- Provide constructive feedback

See [CONTRIBUTING.md](CONTRIBUTING.md#our-values--code-of-conduct) for our full code of conduct.

### Getting Help
- 📖 Check the [documentation](docs/README.md)
- 🐛 [Report issues](https://github.com/akougkas/zulipchat-mcp/issues)
- 💬 Start a [discussion](https://github.com/akougkas/zulipchat-mcp/discussions)
- 🤝 Read [CONTRIBUTING.md](CONTRIBUTING.md) to get involved

---

<div align="center">
  <sub>Built with ❤️ for the Zulip community by contributors around the world</sub>
</div>