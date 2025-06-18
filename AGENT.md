# AI Agent Instructions for ZulipChat MCP

This document provides comprehensive instructions for AI agents helping human users install, configure, and use the ZulipChat MCP server.

## Prerequisites Check

Before starting, verify the user has these tools installed:

1. **uv (required)** - Check with `uv --version`
   - If not installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Git** - For cloning the repository
3. **MCP Client** - Claude Desktop, Continue IDE, or similar

## Installation Guide for Human Users

### Step 1: Clone and Setup Repository

```bash
# Clone the repository
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Install dependencies (uv will create virtual environment automatically)
uv sync
```

### Step 2: Get Zulip API Credentials

Help your user obtain their Zulip credentials:

1. **Visit their Zulip organization** (e.g., `https://company.zulipchat.com`)
2. **Navigate to Settings:**
   - Click profile picture → "Personal settings"
   - Go to "Account & privacy" tab
   - Scroll to "API key" section
3. **Generate API Key:**
   - Click "Generate API key"
   - Copy the API key and email address

### Step 3: Configure Environment

Create a `.env` file in the project root:

```bash
# Create .env file with user's credentials
cat > .env << EOF
ZULIP_SITE=https://your-org.zulipchat.com
ZULIP_EMAIL=user@company.com
ZULIP_API_KEY=their-api-key-here
EOF
```

**Alternative**: Set environment variables directly:
```bash
export ZULIP_SITE="https://your-org.zulipchat.com"
export ZULIP_EMAIL="user@company.com"
export ZULIP_API_KEY="their-api-key-here"
```

### Step 4: Test Installation

```bash
# Load environment and test configuration
export $(cat .env | grep -v '^#' | xargs)

# Test Zulip connection
uv run python -c "
from src.zulipchat_mcp.config import ConfigManager
from src.zulipchat_mcp.client import ZulipClientWrapper
try:
    cm = ConfigManager()
    client = ZulipClientWrapper(cm)
    streams = client.get_streams()
    print(f'✅ Connected to Zulip! Found {len(streams)} streams.')
except Exception as e:
    print(f'❌ Connection failed: {e}')
"

# Optional: Test MCP server startup (will run until interrupted)
uv run python -m src.zulipchat_mcp.server server
```

## MCP Client Configuration

Once the server is tested and working, help the user configure their MCP client:

### Claude Desktop Configuration

1. **Locate Claude Desktop config file:**
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add ZulipChat MCP server configuration:**

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.zulipchat_mcp.server", "server"],
      "cwd": "/full/path/to/zulipchat-mcp",
      "env": {
        "ZULIP_EMAIL": "user@company.com",
        "ZULIP_API_KEY": "their-api-key",
        "ZULIP_SITE": "https://company.zulipchat.com"
      }
    }
  }
}
```

**Important**: Replace `/full/path/to/zulipchat-mcp` with the actual absolute path to the cloned repository.

### Continue IDE Configuration

Add to your Continue config (`~/.continue/config.json`):

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.zulipchat_mcp.server", "server"],
      "cwd": "/full/path/to/zulipchat-mcp",
      "env": {
        "ZULIP_EMAIL": "user@company.com",
        "ZULIP_API_KEY": "their-api-key",
        "ZULIP_SITE": "https://company.zulipchat.com"
      }
    }
  }
}
```

### Alternative: Docker-based Configuration

For users who prefer Docker (may be more reliable):

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "akougkas/zulipchat-mcp:latest"],
      "env": {
        "ZULIP_EMAIL": "user@company.com",
        "ZULIP_API_KEY": "their-api-key", 
        "ZULIP_SITE": "https://company.zulipchat.com"
      }
    }
  }
}
```

## Available MCP Tools

Once configured, the user will have access to these tools in their MCP client:

- **`send_message`** - Send messages to streams or users
- **`get_messages`** - Retrieve messages with filtering
- **`search_messages`** - Search message content
- **`get_streams`** - List available streams
- **`get_users`** - List organization users
- **`add_reaction`** - Add emoji reactions
- **`edit_message`** - Edit existing messages
- **`get_daily_summary`** - Generate activity reports

## Troubleshooting Common Issues

### "No Zulip email found" Error
```bash
# Check if environment variables are set
echo $ZULIP_EMAIL
echo $ZULIP_API_KEY
echo $ZULIP_SITE

# Re-export from .env file
export $(cat .env | grep -v '^#' | xargs)
```

### "Failed to connect to Zulip" Error
1. **Verify credentials** are correct
2. **Check API key** hasn't expired
3. **Confirm site URL** is correct (include https://)
4. **Test network connectivity** to Zulip server

### MCP Client Connection Issues
1. **Check absolute paths** in configuration
2. **Verify uv is available** in the system PATH
3. **Test server manually** before configuring client
4. **Restart MCP client** after configuration changes

### Permission Errors
1. **Check API key permissions** in Zulip settings
2. **Verify bot user** has access to required streams
3. **Test with basic operations** first (get_streams, get_users)

## Testing and Validation

Use these commands to help users verify their setup:

```bash
# Test configuration only
export $(cat .env | grep -v '^#' | xargs)
uv run python -c "from src.zulipchat_mcp.config import ConfigManager; print('✅ Valid' if ConfigManager().validate_config() else '❌ Invalid')"

# Test Zulip connection
uv run python -c "
from src.zulipchat_mcp.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
client = ZulipClientWrapper(ConfigManager())
print(f'Streams: {len(client.get_streams())}')
print(f'Users: {len(client.get_users())}')
"

# Test sending a message
uv run python -c "
from src.zulipchat_mcp.client import ZulipClientWrapper  
from src.zulipchat_mcp.config import ConfigManager
client = ZulipClientWrapper(ConfigManager())
result = client.send_message('stream', 'general', 'Test from MCP!', 'testing')
print('Message sent:', result)
"
```

## AI Agent Slash Commands

### Available Slash Commands

The ZulipChat MCP provides three powerful slash commands for AI agents:

1. **`/zulipchat:summarize`** - Daily summary with message stats and key conversations
2. **`/zulipchat:prepare`** - Morning briefing with yesterday's highlights and weekly overview
3. **`/zulipchat:catch_up`** - Quick catch-up summary for missed messages

### Universal Implementation

Use the shared slash commands script that works with any AI agent:

```bash
# Daily summary (last 24 hours)
uv run slash_commands.py summarize

# Morning briefing with 5-day overview
uv run slash_commands.py prepare general,development 5

# Catch-up for last 4 hours
uv run slash_commands.py catch_up general 4
```

### Claude Code Integration

For Claude Code users, generate the slash command files:

```bash
# Create Claude Code slash commands in ~/.claude/commands/
uv run agents/claude_code_commands.py
```

This creates:
- `~/.claude/commands/zulipchat:summarize.md`
- `~/.claude/commands/zulipchat:prepare.md`
- `~/.claude/commands/zulipchat:catch_up.md`

### Other AI Agents

The `slash_commands.py` script can be integrated with:
- **Cursor IDE**: Call via terminal or custom commands
- **Cascade**: Integrate in workflow scripts
- **Aider**: Use as external tool
- **Other agents**: Any agent that can execute Python scripts

## Development Notes

### Code Structure
- `src/zulipchat_mcp/server.py` - Main MCP server with FastMCP
- `src/zulipchat_mcp/client.py` - Zulip API wrapper with Pydantic models
- `src/zulipchat_mcp/config.py` - Multi-source configuration management
- `slash_commands.py` - Universal slash commands implementation
- `agents/claude_code_commands.py` - Claude Code specific command generator

### Development Commands
```bash
# Install with dev dependencies
uv sync

# Test server locally
export $(cat .env | grep -v '^#' | xargs)
uv run python -m src.zulipchat_mcp.server server

# Test slash commands
uv run slash_commands.py summarize
uv run slash_commands.py prepare general 7
uv run slash_commands.py catch_up 4

# Run tests (if available)
uv run pytest

# Format code
uv run black src/
uv run ruff check src/
```

### Key Features
- **8 MCP Tools** for Zulip operations
- **3 MCP Resources** for data access (messages, streams, users)
- **3 Custom Prompts** for summaries and reports
- **3 Slash Commands** for AI agent integration
- **Universal agent support** via Python script
- **Multiple config sources** (env vars, files, Docker secrets)
- **Comprehensive error handling** and validation