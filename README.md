# ZulipChat MCP Server

<div align="center">
  <!-- TODO: Add banner image showcasing Zulip + AI integration -->
  <!-- <img src="docs/assets/zulipchat-mcp-banner.png" alt="ZulipChat MCP Banner" width="800"> -->

  <h3>Transform your AI assistant into a Zulip power user with 40+ tools via MCP</h3>

  [![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
  [![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
  [![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
  [![Version](https://img.shields.io/badge/Version-2.5.1-green)](https://github.com/akougkas/zulipchat-mcp)
  [![Release](https://img.shields.io/github/v/release/akougkas/zulipchat-mcp)](https://github.com/akougkas/zulipchat-mcp/releases/latest)
  [![Coverage](https://img.shields.io/badge/Coverage-90%25-brightgreen)](https://github.com/akougkas/zulipchat-mcp)
  [![Code Style](https://img.shields.io/badge/Code%20Style-Black-black)](https://github.com/psf/black)

  [🚀 Quick Start](#-quick-start) • [📦 Installation](#-installation) • [📚 Features](#-what-can-you-do) • [🛠️ Tools](#-available-tools) • [💡 Examples](#-real-world-examples) • [📖 Releases](#-releases) • [🤝 Contributing](CONTRIBUTING.md)
</div>

---

## Quick Start

Get your AI assistant connected to Zulip in **30 seconds**:

```bash
# Basic setup (user credentials only)
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site https://org.zulipchat.com
```

**Want advanced AI agent features?** Add bot credentials:
```bash
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site https://org.zulipchat.com \
  --zulip-bot-email bot@org.com \
  --zulip-bot-api-key BOT_API_KEY
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

## Installation

### Choose Your Installation Method

#### Option 1: From PyPI (Recommended - Coming Soon)
```bash
# Basic setup (mandatory parameters)
uvx zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site https://org.zulipchat.com

# With bot for AI agent features (add optional parameters)
uvx zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site https://org.zulipchat.com \
  --zulip-bot-email bot@org.com \
  --zulip-bot-api-key BOT_API_KEY
```

#### Option 2: From GitHub (Available Now)
```bash
# Basic setup
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site https://org.zulipchat.com

# With bot credentials
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site https://org.zulipchat.com \
  --zulip-bot-email bot@org.com \
  --zulip-bot-api-key BOT_API_KEY
```

#### Option 3: From Source (For Development)
```bash
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync

# Run with mandatory parameters
uv run zulipchat-mcp \
  --zulip-email user@org.com \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site https://org.zulipchat.com
```

### MCP Client Integration

<details>
<summary><b>Claude Desktop</b> - Click for configuration</summary>

Add to `claude_desktop_config.json`:

**From PyPI** (once published):
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp"],
      "env": {
        "ZULIP_EMAIL": "bot@your-org.zulipchat.com",
        "ZULIP_API_KEY": "your-api-key",
        "ZULIP_SITE": "https://your-org.zulipchat.com"
      }
    }
  }
}
```

**From GitHub** (available now):
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

</details>

<details>
<summary><b>Claude Code</b> - Click for configuration</summary>

```bash
# From PyPI (once published)
claude mcp add zulipchat \
  -e ZULIP_EMAIL=bot@your-org.zulipchat.com \
  -e ZULIP_API_KEY=your-api-key \
  -e ZULIP_SITE=https://your-org.zulipchat.com \
  -- uvx zulipchat-mcp

# From GitHub (available now)
claude mcp add zulipchat \
  -e ZULIP_EMAIL=bot@your-org.zulipchat.com \
  -e ZULIP_API_KEY=your-api-key \
  -e ZULIP_SITE=https://your-org.zulipchat.com \
  -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp

# From TestPyPI (for testing)
claude mcp add zulipchat \
  -e ZULIP_EMAIL=bot@your-org.zulipchat.com \
  -e ZULIP_API_KEY=your-api-key \
  -e ZULIP_SITE=https://your-org.zulipchat.com \
  -- uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zulipchat-mcp
```

</details>

<details>
<summary><b>Cursor/VS Code/Windsurf</b> - Click for configuration</summary>

Add to your `mcp_config.json` or similar editor specific mcp config file:

**From PyPI** (once published):
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp"],
      "env": {
        "ZULIP_EMAIL": "bot@your-org.zulipchat.com",
        "ZULIP_API_KEY": "your-api-key",
        "ZULIP_SITE": "https://your-org.zulipchat.com"
      }
    }
  }
}
```

**From GitHub** (available now):
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

</details>

## Real-World Examples

### AI-Powered Analytics & Insights
```text
You: "Show me engagement trends for #design this week with top contributors"
AI: Design Channel Analytics (7 days):
    • 40% increase in activity
    • 127 messages (+32% vs last week)
    • Top contributors: Alice (23), Bob (18), Carol (15)
    • Peak activity: Tuesday 2-4pm
    • Hot topics: accessibility (28%), mobile UX (22%)
    • Collaboration score: 9.2/10
```

### Smart Workflow Automation
```text
You: "Schedule weekly standup reminders for #engineering every Monday at 9am"
AI: Automated Standup System Created:
    • Scheduled: Every Monday 9:00 AM
    • Template: Previous week summary + upcoming milestones
    • Auto-includes: Sprint progress & blockers
    • Notifications: Team leads get preview 30min prior
```

### Intelligent File Management
```text
You: "Upload the new design mockups and share them in #design with context for review"
AI: File Upload & Distribution Complete:
    Uploaded: UI_Mockups_v3.2.pdf (4.2MB, 24 pages)
    Auto-detected: Figma export, includes mobile & desktop views
    Shared in #design with:
      • Design review request template
      • @design-leads tagged for approval
      • Comparison links to previous version
      • Review deadline: Next Friday
```

### Advanced Search & Discovery
```text
You: "Find all technical decisions made about authentication in the last month"
AI: Technical Decision Discovery:
    Found 8 authentication-related decisions:
    • OAuth 2.0 implementation (approved - #backend)
    • Multi-factor requirements (pending - #security)
    • Session timeout policies (implemented - #devops)
    • API key rotation (scheduled - #infrastructure)
    Full decision log exported to #documentation
```

### Smart Daily Operations
```text
You: "Generate our comprehensive daily standup for engineering with blockers and sentiment"
AI: Daily Engineering Standup Report:

    Yesterday's Accomplishments (12 contributors):
    • API endpoint refactoring completed (Alice, Bob)
    • Mobile UI bugs fixed (Carol, Dan)
    • Security audit findings addressed (Eve, Frank)

    Current Blockers (3 identified):
    • Database migration pending DBA review
    • Third-party API rate limits affecting tests
    • Design assets needed for new feature

    Team Sentiment: 85% positive
    Energy Level: High (sprint goals on track)
    Notable: Team excited about upcoming hackathon

    Sprint Progress: 68% complete (ahead of schedule)
```

## Releases

### Latest: v2.5.0 - Enhanced Credential Management
**43+ tools** with complete Zulip automation capabilities
- [Release Notes](https://github.com/akougkas/zulipchat-mcp/releases/tag/v2.5.0)
- [Release Documentation](docs/releases/v2.5.0/RELEASE_v2.5.0.md)
- [Full Changelog](https://github.com/akougkas/zulipchat-mcp/blob/main/CHANGELOG.md)

### Previous Versions
- [v1.5.0](https://github.com/akougkas/zulipchat-mcp/releases/tag/v1.5.0) - Project management features
- [v1.0.0](https://github.com/akougkas/zulipchat-mcp/releases/tag/v1.0.0) - Initial release

## ⚙️ Configuration Guide

### Configuration Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `--zulip-email` | Yes | Your Zulip user email | `user@org.com` |
| `--zulip-api-key` | Yes | Your Zulip API key | `abcd1234...` |
| `--zulip-site` | Yes | Your Zulip organization URL | `https://org.zulipchat.com` |
| `--zulip-bot-email` | No | Bot email for AI agent features | `bot@org.com` |
| `--zulip-bot-api-key` | No | Bot API key | `wxyz5678...` |
| `--zulip-bot-name` | No | Custom bot display name | `AI Assistant` |
| `--zulip-bot-avatar-url` | No | Bot avatar image URL | `https://...` |

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

# Copy environment template (never commit secrets)
cp -n .env.example .env || true

# Run locally with credentials
uv run zulipchat-mcp \
  --zulip-email your@email.com \
  --zulip-api-key YOUR_KEY \
  --zulip-site https://yourorg.zulipchat.com
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
uv run pytest -q                  # Tests (90% coverage required)
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

## License

MIT - See [LICENSE](LICENSE) for details.

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