# ZulipChat MCP Commands

This document describes the bundled commands available for AI agents (Claude Code and Gemini CLI) that integrate with the ZulipChat MCP server.

## Overview

The ZulipChat MCP server provides bundled commands that wrap multiple MCP tool operations into convenient slash commands. These commands are installed as native agent commands, eliminating the need for a standalone CLI while maintaining the MCP server's core functionality.

### Available Commands

| Command | Description | Arguments |
|---------|-------------|-----------|
| `/zulipchat:summarize` | Generate daily summary with message stats | `[streams] [hours]` |
| `/zulipchat:prepare` | Morning briefing with yesterday's highlights | `[streams] [days]` |
| `/zulipchat:catch_up` | Quick catch-up for missed messages | `[streams] [hours]` |

## Installation

### Prerequisites

- ZulipChat MCP server installed and configured
- AI agent (Claude Code or Gemini CLI) installed
- Python environment with uv package manager

### Claude Code Installation

Install commands to your Claude Code configuration:

```bash
# Install to default location (~/.claude/commands/zulipchat/)
uv run examples/adapters/setup_agents.py claude

# Install to custom location
uv run examples/adapters/setup_agents.py claude --dir /path/to/custom/dir

# List available commands
uv run examples/adapters/setup_agents.py list
```

### Gemini CLI Installation

Install commands to your Gemini CLI configuration:

```bash
# Install to user scope (default)
uv run examples/adapters/setup_agents.py gemini

# Install to project scope
uv run examples/adapters/setup_agents.py gemini --scope project

# Install to custom location
uv run examples/adapters/setup_agents.py gemini --dir /path/to/custom/dir

# List available commands
uv run examples/adapters/setup_agents.py list
```

### OpenCode Installation

Install commands to your OpenCode configuration:

```bash
# Install to user scope (default)
uv run examples/adapters/setup_agents.py opencode

# Install to project scope
uv run examples/adapters/setup_agents.py opencode --scope project

# Install to custom location
uv run examples/adapters/setup_agents.py opencode --dir /path/to/custom/dir

# List available commands
uv run examples/adapters/setup_agents.py list
```

## Usage Examples

### Claude Code

Once installed, use the commands directly in Claude Code:

```
/zulipchat:summarize
/zulipchat:summarize general,development 48
/zulipchat:prepare
/zulipchat:prepare team,announcements 5
/zulipchat:catch_up
/zulipchat:catch_up general 4
```

### Gemini CLI

Once installed, use the commands directly in Gemini CLI:

```
/zulipchat:summarize
/zulipchat:summarize general,development 48
/zulipchat:prepare
/zulipchat:prepare team,announcements 5
/zulipchat:catch_up
/zulipchat:catch_up general 4
```

### OpenCode

Once installed, use the commands with user or project scope in OpenCode:

```
# User scope commands
/user:zulipchat:summarize
/user:zulipchat:summarize general,development 48
/user:zulipchat:prepare
/user:zulipchat:prepare team,announcements 5
/user:zulipchat:catch_up
/user:zulipchat:catch_up general 4

# Project scope commands (if installed with --scope project)
/project:zulipchat:summarize
/project:zulipchat:prepare
/project:zulipchat:catch_up
```

## Command Details

### /zulipchat:summarize

Generates a comprehensive daily summary of Zulip activity.

**Arguments:**
- `streams` (optional): Comma-separated list of stream names to focus on
- `hours` (optional): Number of hours to look back (default: 24)

**Example Output:**
```
📈 Daily Summary - 2024-01-15

⏱️ Time Range: Last 24 hours
💬 Total Messages: 156

🏞️ Stream Activity
### #general
- Messages: 45
- Active Topics:
  - project-updates: 12 messages
  - team-meeting: 8 messages

👥 Top Contributors
- Alice: 23 messages
- Bob: 18 messages
- Charlie: 15 messages
```

### /zulipchat:prepare

Creates a morning briefing with yesterday's highlights and weekly overview.

**Arguments:**
- `streams` (optional): Comma-separated list of stream names to focus on
- `days` (optional): Number of days for weekly overview (default: 7)

**Example Output:**
```
🌅 Morning Briefing - 2024-01-15

📊 Yesterday's Highlights
💬 Total Messages: 89

🔥 Most Active Streams:
- #general: 45 messages
- #development: 23 messages

📈 Weekly Overview (Last 7 days)
💬 Total Messages: 1,247
📊 Average Daily Messages: 178

👥 Most Active Contributors:
- Alice: 156 messages
- Bob: 134 messages
```

### /zulipchat:catch_up

Generates a quick catch-up summary for missed messages.

**Arguments:**
- `streams` (optional): Comma-separated list of stream names to focus on
- `hours` (optional): Number of hours to look back (default: 8)

**Example Output:**
```
⚡ Catch-Up Summary

📅 Missed Messages from Last 8 Hours

#general (23 messages)
### 💬 Project Updates
- 8 messages from Alice, Bob, Charlie
- Latest: "Updated deployment schedule for next week"

#development (15 messages)
### 💬 Bug Fixes
- 6 messages from Alice, David
- Latest: "Fixed authentication issue in login flow"
```

## Configuration

### Environment Variables

Ensure these environment variables are set for the MCP server:

```bash
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
```

### MCP Server Configuration

The commands require the ZulipChat MCP server to be running and accessible. Configure your AI agent to connect to the MCP server according to your agent's documentation.

## Troubleshooting

### Common Issues

#### Commands Not Found

**Problem:** Commands don't appear in the agent after installation.

**Solutions:**
- Ensure the installation completed successfully
- Check that the command files were created in the correct directory
- Restart your AI agent
- Verify file permissions

#### MCP Connection Failed

**Problem:** Commands fail with connection errors.

**Solutions:**
- Verify Zulip credentials are correct
- Check that the MCP server is running
- Ensure network connectivity to your Zulip instance
- Validate the ZULIP_SITE URL

#### Permission Errors

**Problem:** Installation fails with permission errors.

**Solutions:**
- Run the installation command with appropriate permissions
- Check write access to the target directory
- Use `sudo` if installing to system directories (not recommended)

### Debug Commands

Test your setup with these commands:

```bash
# Test Claude Code adapter
uv run examples/adapters/setup_agents.py list

# Test Gemini CLI adapter
uv run examples/adapters/setup_agents.py list

# Test OpenCode adapter
uv run examples/adapters/setup_agents.py list

# Check MCP server (if available)
uv run python -c "from src.zulipchat_mcp.config import ConfigManager; print('Valid' if ConfigManager().validate_config() else 'Invalid')"
```

### File Locations

**Claude Code:**
- User scope: `~/.claude/commands/zulipchat/`
- Commands: `summarize.md`, `prepare.md`, `catch_up.md`

**Gemini CLI:**
- User scope: `~/.gemini/commands/zulipchat/`
- Project scope: `./.gemini/commands/zulipchat/`
- Commands: `summarize.toml`, `prepare.toml`, `catch_up.toml`

**OpenCode:**
- User scope: `~/.local/opencode/commands/zulipchat/`
- Project scope: `./.opencode/commands/zulipchat/`
- Commands: `summarize.md`, `prepare.md`, `catch_up.md`

## Development

### Adding New Commands

To add new commands:

1. Update the command definitions in both adapter scripts
2. Add the command logic to the MCP server if needed
3. Update this documentation
4. Test with both agents

### Updating Commands

To update existing commands:

1. Modify the command definitions in the adapter scripts
2. Reinstall the commands
3. Restart your AI agent

## Support

For issues with:
- **ZulipChat MCP server**: Check the main project documentation
- **Claude Code**: Refer to [Claude Code documentation](https://docs.anthropic.com/claude-code)
- **Gemini CLI**: Refer to [Gemini CLI documentation](https://gemini.google.com/cli)

Report bugs and request features at: [ZulipChat MCP Issues](https://github.com/akougkas/zulipchat-mcp/issues)