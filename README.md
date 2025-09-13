# ZulipChat MCP Server

<div align="center">

**Transform how AI assistants interact with Zulip Chat**
*Now with 60% better tool-calling accuracy and 37+ powerful tools!*

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Version](https://img.shields.io/badge/Version-2.5.0-green)](https://github.com/akougkas/zulipchat-mcp)
[![Release](https://img.shields.io/github/v/release/akougkas/zulipchat-mcp)](https://github.com/akougkas/zulipchat-mcp/releases/latest)

[🚀 Quick Start](#quick-start) • [📦 Installation](#installation) • [🛠️ Tools](#available-tools-v250) • [💡 Examples](#examples) • [🎉 What's New](https://github.com/akougkas/zulipchat-mcp/releases/latest)

</div>

## What is this?

ZulipChat MCP revolutionizes how AI assistants work with your Zulip workspace. With **37+ intelligent tools** and **comprehensive MCP optimization**, your AI can now handle complex workflows, generate insights, and automate tasks with unprecedented accuracy.

### Real-World Magic

```text
You: "Generate our daily standup report for #engineering with sentiment analysis"
AI: Created comprehensive standup:
    • 12 contributors, 8 tasks completed
    • Team sentiment: 85% positive
    • 3 blockers identified with solutions

You: "Cross-post the deployment update to product and support teams"
AI: Shared across streams with context:
    • #product (tagged @product-leads)
    • #support (included timeline & rollback plan)

You: "Show engagement trends for our design discussions this week"
AI: Design Analytics:
    • 40% increase in participation
    • Top collaborators: Alice, Bob, Carol
    • Trending: accessibility, mobile UX
```

## Version 2.5.0: The AI Assistant Revolution

**The biggest update yet!** v2.5.0 transforms your AI assistant's Zulip capabilities with unprecedented intelligence and reliability.

### **What Makes This Special**

- **60% Smarter AI Integration**: Completely optimized tool descriptions using latest MCP best practices
- **37+ Powerful Tools**: From basic messaging to advanced analytics and file management
- **Security First**: Enhanced permission boundaries and secure-by-default architecture
- **Modern FastMCP 2.12.3**: Latest framework with advanced features and better performance
- **Advanced Analytics**: AI-powered insights, sentiment analysis, and engagement tracking
- **Seamless Workflows**: Cross-stream sharing, bulk operations, and automated reporting
- **Smart File Management**: Secure uploads with auto-sharing and metadata extraction

## 🛠️ Available Tools (v2.5.0)

**37+ intelligent tools** organized into powerful categories. Each tool is optimized for maximum AI understanding and reliability.

### **Advanced Messaging** (8 tools)
| Tool | New Capabilities |
|------|------------------|
| `message` | Send, schedule, or draft messages with **smart formatting** and **delivery options** |
| `search_messages` | **Token-limited results** with **narrow filters** and **advanced queries** |
| `edit_message` | Edit content + topics with **propagation modes** and **notification control** |
| `bulk_operations` | **Progress tracking** for bulk actions across multiple messages |
| `message_history` | Complete **audit trail** with **edit timestamps** and **revision tracking** |
| `cross_post_message` | **Attribution-aware** sharing across streams with **context preservation** |
| `add_reaction` / `remove_reaction` | **Emoji type support** (Unicode, custom, Zulip extra) |

### **Stream & Topic Management** (5 tools)
| Tool | New Capabilities |
|------|------------------|
| `manage_streams` | **Lifecycle management** with permissions, **bulk subscriptions** |
| `manage_topics` | **Cross-stream transfers** with **propagation modes** and notifications |
| `get_stream_info` | **Comprehensive details** with subscriber lists and topic inclusion |
| `stream_analytics` | **NEW!** Growth trends, engagement metrics, subscriber activity |
| `manage_stream_settings` | **NEW!** Notification preferences, appearance, permissions |

### **Real-Time Events** (3 tools)
| Tool | New Capabilities |
|------|------------------|
| `register_events` | **20+ event types** with **auto-cleanup** and **queue management** |
| `get_events` | **Long-polling support** with **queue validation** and error handling |
| `listen_events` | **NEW!** Webhook integration, event filtering, stateless operation |

### **User & Identity Management** (3 tools)
| Tool | New Capabilities |
|------|------------------|
| `manage_users` | **Multi-identity support** (user/bot/admin contexts) |
| `switch_identity` | **NEW!** Session continuity with validation and capability tracking |
| `manage_user_groups` | **NEW!** Complete group lifecycle with membership management |

### **Advanced Search & Analytics** (3 tools)
| Tool | New Capabilities |
|------|------------------|
| `advanced_search` | **NEW!** Multi-faceted search with **intelligent ranking** and **aggregation** |
| `analytics` | **NEW!** AI-powered insights with **sentiment analysis** and **participation metrics** |
| `get_daily_summary` | **NEW!** Comprehensive activity summaries with **stream engagement** |

### **File & Media Management** (2 tools)
| Tool | New Capabilities |
|------|------------------|
| `upload_file` | **NEW!** Progress tracking, **auto-sharing**, **security validation** |
| `manage_files` | **NEW!** Complete file lifecycle with **metadata extraction** |

### **Agent Communication** (13 tools)
| Tool | New Capabilities |
|------|------------------|
| `register_agent` | **NEW!** Database persistence with **session tracking** |
| `agent_message` | **NEW!** BOT identity messaging with **AFK gating** |
| `request_user_input` | **NEW!** Interactive workflows with **intelligent routing** |
| `start_task` / `update_progress` / `complete_task` | **NEW!** Full task lifecycle management |
| `enable_afk_mode` / `disable_afk_mode` | **NEW!** Away-mode automation |
| *...and 6 more agent tools* | Advanced workflow automation and monitoring |

### **System & Workflow** (6 tools)
| Tool | New Capabilities |
|------|------------------|
| `server_info` | **NEW!** Comprehensive metadata with **routing hints** |
| `tool_help` | **NEW!** On-demand documentation with **module search** |
| `execute_chain` | **NEW!** Sophisticated workflow automation with **branching logic** |
| *...and 3 more system tools* | Identity policy, agent bootstrapping, command types |

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

## Examples: See the Magic in Action

### **AI-Powered Analytics & Insights**
```text
You: "Analyze team sentiment around our Q4 goals across all channels"
AI: Sentiment Analysis Complete:
    • Overall sentiment: 82% positive
    • #engineering: Optimistic about delivery
    • #product: Concerns about timeline
    • #design: Excited about new features
    • Suggestion: Schedule sync on timeline expectations

You: "Show me engagement trends for #design this week with top contributors"
AI: Design Channel Analytics (7 days):
    • 40% increase in activity
    • 127 messages (+32% vs last week)
    • Top contributors: Alice (23), Bob (18), Carol (15)
    • Peak activity: Tuesday 2-4pm
    • Hot topics: accessibility (28%), mobile UX (22%)
    • Collaboration score: 9.2/10
```

### **Smart Workflow Automation**
```text
You: "Cross-post the deployment update from #devops to product and support teams with relevant context"
AI: Deployment Update Shared:
    • #product: Added impact on user-facing features
    • #support: Included troubleshooting guide & rollback procedure
    • #leadership: Executive summary with business metrics
    • All posts tagged relevant teams and stakeholders

You: "Schedule weekly standup reminders for #engineering every Monday at 9am"
AI: Automated Standup System Created:
    • Scheduled: Every Monday 9:00 AM
    • Template: Previous week summary + upcoming milestones
    • Auto-includes: Sprint progress & blockers
    • Notifications: Team leads get preview 30min prior
```

### **Intelligent File Management**
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

### **Advanced Search & Discovery**
```text
You: "Find all technical decisions made about authentication in the last month"
AI: Technical Decision Discovery:
    Found 8 authentication-related decisions:
    • OAuth 2.0 implementation (approved - #backend)
    • Multi-factor requirements (pending - #security)
    • Session timeout policies (implemented - #devops)
    • API key rotation (scheduled - #infrastructure)
    Full decision log exported to #documentation

You: "Search for mentions of 'performance issues' and categorize by severity"
AI: Performance Issues Analysis:
    High Priority (3 issues):
    • Database query timeouts - #backend
    • Mobile app crashes - #mobile
    Critical Priority (1 issue):
    • Production API latency spikes - #devops
    Trend: 40% increase vs last month
    Recommended: Performance review meeting
```

### **Smart Daily Operations**
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
