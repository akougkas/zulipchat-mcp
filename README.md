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

- **Teleport-Chat** - Private back-channel DMs (bot identity) + public messaging as you (user identity)
- **Fuzzy User Resolution** - "text Jaime" just works — no hunting for formal Zulip emails
- **Intelligent Messaging** - Send, schedule, search, and manage messages with context awareness
- **Real-time Monitoring** - Always-on listener receives DMs + all streams automatically
- **Advanced Analytics** - Generate insights, sentiment analysis, and participation reports
- **File Operations** - Upload, share, and manage files with automatic distribution
- **Workflow Automation** - Chain complex operations with conditional logic

## Available Tools

67 tools across 8 categories:

| Category | Count | Highlights |
|----------|-------|------------|
| **Messaging** | 15 | Send, edit, schedule, cross-post, reactions |
| **Streams & Topics** | 4 | Stream info, topic management |
| **Users & Identity** | 14 | Fuzzy name resolution, presence, groups, dual identity |
| **Agent Communication** | 14 | **Teleport-chat**, bidirectional DMs, task tracking, AFK mode |
| **Search & Analytics** | 8 | Narrow filters, AI insights, summaries |
| **Events** | 4 | Queues, long-polling, webhooks |
| **Files** | 2 | Upload, share, download, manage |
| **System & Workflows** | 6 | Identity switching, command chains |

<details>
<summary>View all tools by category</summary>

### Messaging Tools
- `message` - Send, schedule, or draft messages with smart formatting
- `search_messages` - Token-limited results with narrow filters
- `edit_message` - Edit content and topics with propagation modes
- `bulk_operations` - Progress tracking for bulk actions
- `message_history` - Audit trail with edit timestamps
- `cross_post_message` - Attribution-aware sharing across streams
- `add_reaction` / `remove_reaction` - Emoji support (Unicode, custom, Zulip)
- `mark_read` / `mark_unread` - Read state management
- `schedule_message` / `cancel_scheduled` - Delayed delivery

### Stream & Topic Tools
- `get_stream_info` - Stream details with subscriber lists
- `list_streams` - Filter by subscription status
- `list_topics` - Topics within a stream
- `manage_topics` - Cross-stream transfers with propagation

### User Tools
- `resolve_user` - **NEW** Fuzzy name-to-email resolution ("Jaime" → email)
- `manage_users` - Multi-identity support (user/bot contexts)
- `switch_identity` - Session continuity with validation
- `manage_user_groups` - Group lifecycle and membership
- `get_presence` - User online status
- `set_status` - Status emoji and text
- `mute_user` / `unmute_user` - User muting

### Search & Analytics Tools
- `advanced_search` - Multi-faceted search with ranking
- `analytics` - AI-powered insights with sentiment analysis
- `get_daily_summary` - Activity summaries with engagement

### Event Tools
- `register_events` - 20+ event types with auto-cleanup
- `get_events` - Long-polling with queue validation
- `delete_queue` - Queue cleanup
- `listen_events` - Webhook integration

### File Tools
- `upload_file` - Progress tracking with auto-sharing
- `manage_files` - File lifecycle with metadata extraction

### Agent & Communication Tools
- `teleport_chat` - **NEW** Send message to user/channel with identity-aware routing
- `register_agent` - Agent session tracking
- `agent_message` - Bot identity messaging
- `poll_agent_events` - Receive user replies (DMs + streams)
- `enable_afk_mode` / `disable_afk_mode` - AFK notifications with auto-return

### System & Workflow Tools
- `server_info` - Server metadata with routing hints
- `execute_chain` - Workflow automation with branching logic

</details>

## Installation

One command to connect your AI to Zulip:

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

<details>
<summary><b>Setup Wizard</b> - guided configuration</summary>

```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

The wizard finds your zuliprc files, validates credentials, and generates MCP client config.
</details>

<details>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

With dual identity (user + bot):
```bash
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```
</details>

<details>
<summary><b>Gemini CLI / Claude Desktop / Cursor</b></summary>

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
</details>

<details>
<summary><b>Getting your zuliprc</b></summary>

Download from Zulip: **Settings** > **Personal settings** > **Account & privacy** > **API key**
</details>

<details>
<summary><b>Configuration options</b></summary>

| Option | Description |
|--------|-------------|
| `--zulip-config-file PATH` | Path to your primary zuliprc |
| `--zulip-bot-config-file PATH` | Optional bot zuliprc for dual identity |
| `--unsafe` | Enable administrative tools (use with caution) |
| `--debug` | Enable debug logging (outputs to stderr) |
</details>

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