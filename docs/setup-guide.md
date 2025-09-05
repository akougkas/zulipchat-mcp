# ZulipChat MCP Setup Guide

This guide provides detailed instructions for setting up the ZulipChat MCP server using UV.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- Zulip organization access
- API key from your Zulip organization

## Installation

### One Command Install

```bash
# Install via uvx (recommended)
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

### Automated Installation

```bash
# One-line installer
curl -fsSL https://raw.githubusercontent.com/akougkas/zulipchat-mcp/main/install.sh | bash
```

### Manual Installation

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Install dependencies
uv sync

# Run the server
uv run zulipchat-mcp
```

## Configuration

### Environment Variables

Set these environment variables before starting the server:

```bash
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
```

### Configuration File

Create `~/.config/zulipchat-mcp/config.json`:

```json
{
  "email": "your-bot@zulip.com",
  "api_key": "your-api-key",
  "site": "https://your-org.zulipchat.com"
}
```

Alternative locations:
- `~/.zulipchat-mcp.json`
- `./config.json` (in working directory)

## Platform-Specific Instructions

### Linux

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install and run
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

### macOS

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install and run
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

### Windows

```powershell
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install and run
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

## MCP Client Configuration

### Claude Desktop

Edit your `claude_desktop_config.json`:

#### macOS
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

#### Windows
```bash
%APPDATA%\Claude\claude_desktop_config.json
```

Add this configuration:

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/akougkas/zulipchat-mcp.git", "zulipchat-mcp"],
      "env": {
        "ZULIP_EMAIL": "your-bot@zulip.com",
        "ZULIP_API_KEY": "your-api-key",
        "ZULIP_SITE": "https://your-org.zulipchat.com"
      }
    }
  }
}
```

### Continue IDE

Add to your `.continue/config.json`:

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/akougkas/zulipchat-mcp.git", "zulipchat-mcp"],
      "env": {
        "ZULIP_EMAIL": "your-bot@zulip.com",
        "ZULIP_API_KEY": "your-api-key",
        "ZULIP_SITE": "https://your-org.zulipchat.com"
      }
    }
  }
}
```

## Verification

### Test Configuration

```bash
# Test UV installation
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git \
  python -c "from src.zulipchat_mcp import __version__; print(__version__)"

# Test connection with your credentials
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"

uv run --from git+https://github.com/akougkas/zulipchat-mcp.git \
  python -c "from src.zulipchat_mcp.config import ConfigManager; print('✅ Valid' if ConfigManager().validate_config() else '❌ Invalid')"
```

### Check Server Status

```bash
# Run the server
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

## Troubleshooting

### Common Issues

**UV not found**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Python version too old**
```bash
# Check Python version
python3 --version  # Should be 3.10+

# Update Python if needed
# On Ubuntu/Debian:
sudo apt update && sudo apt install python3.10
```

**Invalid credentials**
- Double-check your API key, email, and site URL
- Ensure the API key has necessary permissions
- Verify the site URL format (must include https://)

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Environment variable
export MCP_DEBUG=true

# Run with debug
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

### Getting Help

1. Check the [troubleshooting section](../README.md#troubleshooting) in README
2. View [common issues](https://github.com/akougkas/zulipchat-mcp/issues) on GitHub
3. Create a new issue with:
   - Your platform (Linux/macOS/Windows)
   - Installation method used
   - Error messages (with sensitive info redacted)
   - Steps to reproduce