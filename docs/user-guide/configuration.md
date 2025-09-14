# Configuration Guide

Complete configuration guide for ZulipChat MCP v2.5.0 including credentials, identity management, and server settings.

## Configuration Overview

ZulipChat MCP uses a flexible configuration system with three priority levels:

1. **CLI Arguments** (Highest priority)
2. **Environment Variables** (Middle priority)
3. **Default Values** (Fallback)

## Complete CLI Arguments Reference

All available CLI arguments (from actual `server.py` implementation):

```bash
# View all available CLI arguments
uv run python -m src.zulipchat_mcp.server --help

# Required credentials
--zulip-email             # Zulip email address
--zulip-api-key          # Zulip API key
--zulip-site             # Zulip site URL (e.g., https://yourorg.zulipchat.com)

# Optional bot credentials
--zulip-bot-email        # Bot email for advanced features (optional)
--zulip-bot-api-key      # Bot API key (optional)
--zulip-bot-name         # Bot display name (default: "Claude Code")
--zulip-bot-avatar-url   # Bot avatar URL (optional)

# Debug and service options
--debug                  # Enable debug logging
--enable-listener        # Enable Zulip message listener service

# Note: --port and --host arguments do NOT exist in the actual implementation
```

## Required Configuration

### Core Zulip Credentials

These credentials are **required** for basic functionality:

| Environment Variable | CLI Argument | Description | Example |
|---------------------|--------------|-------------|---------|
| `ZULIP_EMAIL` | `--zulip-email` | Your Zulip email address | `user@example.com` |
| `ZULIP_API_KEY` | `--zulip-api-key` | Your Zulip API key | `zulip_abc123def456...` |
| `ZULIP_SITE` | `--zulip-site` | Zulip organization URL | `https://yourorg.zulipchat.com` |

### Getting Your Zulip Credentials

1. **Login to your Zulip organization**
2. **Go to Personal Settings** → Account & Privacy
3. **Generate API key** or copy existing key
4. **Note your email and organization URL**

### Basic Environment Setup

Create a `.env` file or set environment variables:

```bash
# Required credentials
export ZULIP_EMAIL="your-email@example.com"
export ZULIP_API_KEY="your_zulip_api_key_here"  
export ZULIP_SITE="https://yourorg.zulipchat.com"
```

## Optional Configuration

### Bot Identity Configuration

For advanced features like automated agents:

| Environment Variable | CLI Argument | Default | Description |
|---------------------|--------------|---------|-------------|
| `ZULIP_BOT_EMAIL` | `--zulip-bot-email` | None | Bot email for automation |
| `ZULIP_BOT_API_KEY` | `--zulip-bot-api-key` | None | Bot API authentication key |
| `ZULIP_BOT_NAME` | `--zulip-bot-name` | "Claude Code" | Bot display name |
| `ZULIP_BOT_AVATAR_URL` | `--zulip-bot-avatar-url` | None | Bot avatar image URL |

### Server Configuration

| Environment Variable | CLI Argument | Default | Description |
|---------------------|--------------|---------|-------------|
| `MCP_DEBUG` | `--debug` | False | Enable debug logging |
| `MCP_PORT` | (none) | 3000 | MCP server port (environment only) |

### Advanced Options

| Environment Variable | CLI Argument | Default | Description |
|---------------------|--------------|---------|-------------|
| (none) | `--enable-listener` | False | Enable message listener service |

## Identity Management

ZulipChat MCP supports three distinct identity types with different capabilities:

### 1. User Identity (Default)

Standard user permissions for interactive operations:

**Capabilities:**
- Send and read messages  
- Edit own messages
- Search messages and streams
- Upload files
- Subscribe to streams
- Add reactions
- Manage personal preferences

**Configuration:**
```bash
# Only requires basic credentials
ZULIP_EMAIL="user@example.com"
ZULIP_API_KEY="user_api_key"
ZULIP_SITE="https://org.zulipchat.com"
```

### 2. Bot Identity

Automated agent permissions for programmatic operations:

**Capabilities:**
- Send automated messages
- React to messages  
- Stream events
- Schedule messages
- Bulk read operations
- Webhook integration
- Automated responses

**Configuration:**
```bash
# Requires bot credentials
ZULIP_BOT_EMAIL="bot@example.com"
ZULIP_BOT_API_KEY="bot_api_key"  
ZULIP_BOT_NAME="My Assistant Bot"
ZULIP_SITE="https://org.zulipchat.com"
```

### 3. Admin Identity

Full administrative permissions (automatically detected):

**Capabilities:**
- All user and bot capabilities
- User management
- Realm/organization settings
- Data export and import
- Stream administration
- Organization customization

**Configuration:**
```bash
# Uses admin user credentials
ZULIP_EMAIL="admin@example.com"
ZULIP_API_KEY="admin_api_key"
ZULIP_SITE="https://org.zulipchat.com"
```

## Configuration Validation

The system validates configuration on startup:

### Validation Rules

| Field | Validation |
|-------|------------|
| `ZULIP_EMAIL` | Must contain '@' character |
| `ZULIP_API_KEY` | Minimum 10 characters |
| `ZULIP_SITE` | Must start with `http://` or `https://` |
| Bot credentials | Optional but validated if provided |

### Testing Configuration

```bash
# Test basic connectivity
python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
result = client.client.get_server_settings()
print('✓ Connection successful')
print(f'Server: {result[\"realm_name\"]}')
"

# Test authentication
python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
result = client.client.get_profile()
print('✓ Authentication successful')
print(f'User: {result[\"full_name\"]} ({result[\"email\"]})')
"
```

## Server Startup Examples

### Basic Startup

```bash
# Using environment variables
uv run python -m src.zulipchat_mcp.server

# Using CLI arguments
uv run python -m src.zulipchat_mcp.server \
  --zulip-email user@example.com \
  --zulip-api-key your_api_key \
  --zulip-site https://yourorg.zulipchat.com
```

### Development Mode

```bash
# Enable debug logging
uv run python -m src.zulipchat_mcp.server --debug

# Enable message listener
uv run python -m src.zulipchat_mcp.server --enable-listener

# Combined options
uv run python -m src.zulipchat_mcp.server --debug --enable-listener
```

### Production Mode

```bash
# Production configuration
export ZULIP_EMAIL="bot@myorg.com"
export ZULIP_API_KEY="production_api_key"
export ZULIP_SITE="https://myorg.zulipchat.com"
export MCP_PORT=3000

# Start server
uv run python -m src.zulipchat_mcp.server
```

## Multi-Identity Setup

For advanced use cases requiring multiple identity types:

### Dual Identity Configuration

```bash
# User identity (primary)
export ZULIP_EMAIL="user@example.com"
export ZULIP_API_KEY="user_api_key"

# Bot identity (secondary)  
export ZULIP_BOT_EMAIL="assistant@example.com"
export ZULIP_BOT_API_KEY="bot_api_key"

# Organization
export ZULIP_SITE="https://example.zulipchat.com"
```

### Dynamic Identity Switching

The system supports runtime identity switching:

```python
# Switch to bot identity for automation
await switch_identity("bot", validate_credentials=True)

# Switch back to user identity  
await switch_identity("user")

# Use admin identity (if available)
await switch_identity("admin")
```

## Security Best Practices

### Credential Management

```bash
# ✅ Good: Use environment variables
export ZULIP_API_KEY="your_key_here"

# ✅ Good: Use .env files (not committed to git)
echo "ZULIP_API_KEY=your_key_here" > .env

# ❌ Bad: Hardcode in scripts
python -m server --zulip-api-key hardcoded_key  # DON'T DO THIS
```

### File Permissions

```bash
# Secure .env file permissions
chmod 600 .env

# Secure configuration directory
chmod 700 ~/.config/zulipchat-mcp/
```

### API Key Rotation

```bash
# Regularly rotate API keys
# 1. Generate new key in Zulip
# 2. Update environment variable
# 3. Restart server
# 4. Revoke old key
```

## Configuration Files

### Supported Locations

```
# System-wide configuration
/etc/zulipchat-mcp/config.env

# User-specific configuration
~/.config/zulipchat-mcp/config.env
~/.zulipchat-mcp.env

# Project-specific configuration
./.env
./config.env
```

### Configuration File Format

```bash
# ZulipChat MCP Configuration
# Core credentials (required)
ZULIP_EMAIL=user@example.com
ZULIP_API_KEY=your_api_key_here
ZULIP_SITE=https://yourorg.zulipchat.com

# Optional bot configuration
ZULIP_BOT_EMAIL=bot@example.com
ZULIP_BOT_API_KEY=bot_api_key_here
ZULIP_BOT_NAME=Assistant Bot

# Server settings
MCP_DEBUG=false
MCP_PORT=3000

# Note: Message listener is enabled via CLI --enable-listener flag only
```

## Troubleshooting Configuration

### Common Configuration Errors

**Missing Required Variables**
```
Error: Missing required environment variable: ZULIP_EMAIL
Solution: Set all required variables (EMAIL, API_KEY, SITE)
```

**Invalid URL Format**
```
Error: ZULIP_SITE must start with http:// or https://
Solution: Include protocol in URL
```

**Authentication Failure**
```
Error: 401 Unauthorized
Solution: Verify email/API key combination
```

**Bot Configuration Issues**
```
Error: Bot credentials invalid
Solution: Ensure bot is created in Zulip and credentials match
```

### Configuration Validation Commands

```bash
# Check environment variables
env | grep ZULIP

# Test core components (instead of --validate-config which doesn't exist)
python -c "
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
if config.validate_config():
    print('✓ Configuration valid')
else:
    print('❌ Configuration invalid')
"

# Test client connection
python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
print(f'✓ Client initialized with identity: {client.identity_name}')
"
```

## Environment-Specific Configuration

### Development Environment

```bash
# .env.development
ZULIP_EMAIL=dev@example.com
ZULIP_API_KEY=dev_api_key  
ZULIP_SITE=https://dev.zulipchat.com
MCP_DEBUG=true
MCP_PORT=3001
# Note: Cache TTL and other advanced options not yet configurable
```

### Testing Environment

```bash  
# .env.test
ZULIP_EMAIL=test@example.com
ZULIP_API_KEY=test_api_key
ZULIP_SITE=https://test.zulipchat.com
MCP_DEBUG=true
# Note: Rate limiting not yet configurable
```

### Production Environment

```bash
# .env.production  
ZULIP_EMAIL=prod@example.com
ZULIP_API_KEY=secure_prod_key
ZULIP_SITE=https://prod.zulipchat.com
MCP_DEBUG=false
MCP_PORT=3000
# Note: Cache TTL and other advanced options not yet configurable
```

## Validated CLI Integration Commands

These commands have been verified against the actual implementation:

```bash
# Claude Code integration (validated commands)
# From PyPI (once published)
claude mcp add zulipchat \
  -e ZULIP_EMAIL=your@email.com \
  -e ZULIP_API_KEY=your_api_key \
  -e ZULIP_SITE=https://yourorg.zulipchat.com \
  -- uvx zulipchat-mcp

# From GitHub (available now)
claude mcp add zulipchat \
  -e ZULIP_EMAIL=your@email.com \
  -e ZULIP_API_KEY=your_api_key \
  -e ZULIP_SITE=https://yourorg.zulipchat.com \
  -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp

# With bot credentials and debug mode
claude mcp add zulipchat \
  -e ZULIP_EMAIL=user@yourorg.com \
  -e ZULIP_API_KEY=user_key \
  -e ZULIP_BOT_EMAIL=bot@yourorg.com \
  -e ZULIP_BOT_API_KEY=bot_key \
  -e ZULIP_SITE=https://yourorg.zulipchat.com \
  -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp --debug --enable-listener
```

**Note**: Environment variables must come before the `--` separator. CLI arguments for the server go after the package name.

---

**Next**: [Quick Start Guide](quick-start.md) - Start using ZulipChat MCP