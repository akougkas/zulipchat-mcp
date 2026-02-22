# Configuration Guide

Complete configuration guide for ZulipChat MCP v0.5.1.

## Quick Start

The fastest way to get started:

```bash
# Run the setup wizard
uvx --from zulipchat-mcp zulipchat-mcp-setup

# Or use your existing zuliprc
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Authentication Methods

ZulipChat MCP supports two authentication methods:

### Method 1: Zuliprc File (Recommended)

The most secure approach - credentials stay in a file, not exposed in environment or command line.

**Get your zuliprc:**
1. Log into your Zulip organization
2. Go to **Settings** → **Personal settings** → **Account & privacy**
3. Click **Show/change your API key** → **Download .zuliprc**
4. Save to `~/.zuliprc`

**Run with zuliprc:**
```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

**Zuliprc file format:**
```ini
[api]
email=your-email@example.com
key=your_api_key_here
site=https://yourorg.zulipchat.com
```

**Auto-discovery:** If no `--zulip-config-file` is provided, the server searches:
1. `./zuliprc` (current directory)
2. `~/.zuliprc` (home directory)
3. `~/.config/zulip/zuliprc`

### Method 2: Environment Variables (Fallback)

For environments where zuliprc files aren't practical:

```bash
export ZULIP_EMAIL="your-email@example.com"
export ZULIP_API_KEY="your_api_key_here"
export ZULIP_SITE="https://yourorg.zulipchat.com"

uvx zulipchat-mcp
```

## CLI Arguments Reference

```bash
uvx zulipchat-mcp --help

# Configuration
--zulip-config-file PATH      # Path to user zuliprc file
--zulip-bot-config-file PATH  # Path to bot zuliprc (for dual identity)

# Modes
--unsafe                       # Enable dangerous tools (delete, mass unsubscribe)
--debug                        # Enable debug logging
--enable-listener              # Enable background message listener
```

## Dual Identity Setup

For advanced use cases, configure both user and bot identities:

**Using two zuliprc files:**
```bash
uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

**Using environment variables:**
```bash
# User identity (primary - for reading/search)
export ZULIP_EMAIL="user@example.com"
export ZULIP_API_KEY="user_api_key"

# Bot identity (secondary - for posting)
export ZULIP_BOT_EMAIL="bot@example.com"
export ZULIP_BOT_API_KEY="bot_api_key"

# Organization
export ZULIP_SITE="https://yourorg.zulipchat.com"
```

**Runtime switching:**
```python
# Use the switch_identity tool
await switch_identity("bot")   # Switch to bot for automated messages
await switch_identity("user")  # Switch back to user
```

## MCP Client Configurations

### Claude Code

```bash
# Simple setup with zuliprc
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc

# With dual identity
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot

# With environment variables (if no zuliprc)
claude mcp add zulipchat \
  -e ZULIP_EMAIL=you@example.com \
  -e ZULIP_API_KEY=your_key \
  -e ZULIP_SITE=https://yourorg.zulipchat.com \
  -- uvx zulipchat-mcp
```

### Gemini CLI

```bash
# Add to Gemini CLI
gemini mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

### Claude Desktop / Cursor / VS Code

Add to your MCP configuration JSON file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Cursor:** `~/.cursor/mcp.json`
**VS Code:** `.vscode/mcp.json` or user settings

**Using zuliprc (recommended):**
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp", "--zulip-config-file", "/absolute/path/to/zuliprc"]
    }
  }
}
```

**With dual identity:**
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-config-file", "/home/user/.zuliprc",
        "--zulip-bot-config-file", "/home/user/.zuliprc-bot"
      ]
    }
  }
}
```

**Using environment variables:**
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp"],
      "env": {
        "ZULIP_EMAIL": "your-email@example.com",
        "ZULIP_API_KEY": "your_api_key",
        "ZULIP_SITE": "https://yourorg.zulipchat.com"
      }
    }
  }
}
```

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `ZULIP_EMAIL` | User email address | `user@example.com` |
| `ZULIP_API_KEY` | User API key | `abc123...` |
| `ZULIP_SITE` | Organization URL | `https://org.zulipchat.com` |
| `ZULIP_BOT_EMAIL` | Bot email (optional) | `bot@example.com` |
| `ZULIP_BOT_API_KEY` | Bot API key (optional) | `xyz789...` |
| `ZULIP_CONFIG_FILE` | Path to user zuliprc | `~/.zuliprc` |
| `ZULIP_BOT_CONFIG_FILE` | Path to bot zuliprc | `~/.zuliprc-bot` |
| `MCP_DEBUG` | Enable debug logging | `true` / `false` |
| `MCP_PORT` | Server port (internal) | `3000` |

## Safety Modes

**Safe Mode (Default):**
- Restricts dangerous operations
- Cannot delete messages, users, or streams
- Cannot perform mass unsubscribe operations

**Unsafe Mode (`--unsafe`):**
- Enables all administrative tools
- Use with caution in production

```bash
# Enable unsafe mode
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --unsafe
```

## Testing Your Configuration

```bash
# Test connection
uv run python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
print(f'Connected as: {client.identity_name}')
"
```

## Troubleshooting

**"No Zulip configuration found"**
- Ensure zuliprc exists at specified path or standard locations
- Or set ZULIP_EMAIL, ZULIP_API_KEY, ZULIP_SITE environment variables

**"401 Unauthorized"**
- Verify API key is correct (regenerate in Zulip settings if needed)
- Check email matches the account that generated the API key

**"Connection failed"**
- Verify ZULIP_SITE includes `https://`
- Check network connectivity to your Zulip server

**"Bot credentials not configured"**
- Create a bot in Zulip: Organization settings → Bots → Add bot
- Download its zuliprc and use with `--zulip-bot-config-file`

## Security Best Practices

1. **Use zuliprc files** instead of environment variables when possible
2. **Secure file permissions:** `chmod 600 ~/.zuliprc`
3. **Never commit credentials** to version control
4. **Rotate API keys** regularly (regenerate in Zulip settings)
5. **Use Safe Mode** unless you specifically need destructive operations

---

**Next**: [Quick Start Guide](quick-start.md)
