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

## New in v1.4.0: Agent Communication System

**Multi-Instance Bot Identity** - Claude Code now intelligently detects your project and machine context:
- 🏷️ **Automatic Project Detection** - Identifies current project from git, package.json, etc.
- 🖥️ **Machine Awareness** - Different topics for same project on different machines
- 🌳 **Branch Tracking** - Feature branches get distinct notification topics
- 📱 **Personal Streams** - One stream per agent type (claude-code, gemini, etc.)
- 📂 **Project Topics** - Each project gets its own topic within your personal stream

**AFK Mode** - Control when you receive notifications:
- 🚶 **Away Mode** - Only send notifications when you're away from keyboard
- 💻 **Quiet Mode** - Silent operation when you're actively working
- ⏰ **Auto-Return** - Automatically deactivate after specified hours
- 🎯 **Smart Routing** - Messages go to right project topic automatically

**Agent Tools** - New capabilities for AI agents:
- `register_agent` - Register with automatic instance detection
- `agent_message` - Send project-aware notifications
- `request_user_input` - Request input with context
- `start_task` / `complete_task` - Full task lifecycle
- `list_instances` - See all active Claude Code instances
- Stream and topic management tools

See [BOT_SETUP.md](BOT_SETUP.md) for bot identity setup.

## Quick Start

### Claude Code (Recommended)
```bash
# Add with one command:
claude mcp add zulipchat -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp

# Set your credentials:
export ZULIP_EMAIL="bot@your-org.zulipchat.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
```

### Manual Setup
**1. Get your Zulip API key**
```
Visit your Zulip → Settings → Account & Privacy → API Key → Generate
```

**2. Install and run**
```bash
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
from src.zulipchat_mcp.client import ZulipClientWrapper
client = ZulipClientWrapper()
print(f'Connected! Found {len(client.get_streams())} streams.')
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

## Use Cases

- **DevOps**: Automate deployment notifications and incident updates
- **Support**: Route customer questions and create ticket summaries
- **Product**: Generate sprint reports and feature request digests
- **Team Leads**: Daily standups and team activity summaries
- **HR**: Onboarding workflows and announcement automation

## Architecture

ZulipChat MCP is built with:
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [Pydantic](https://pydantic.dev) - Data validation
- [UV](https://docs.astral.sh/uv/) - Fast Python package management
- Async operations for performance
- Smart caching for efficiency
- Comprehensive error handling

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