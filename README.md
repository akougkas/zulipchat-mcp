# ZulipChat MCP Server

<div align="center">
  **Connect AI agents to Zulip Chat with ease**
  
  [![Docker](https://img.shields.io/docker/v/akougkas2030/zulipchat-mcp?label=docker&logo=docker)](https://hub.docker.com/r/akougkas2030/zulipchat-mcp)
  [![Docker Pulls](https://img.shields.io/docker/pulls/akougkas2030/zulipchat-mcp?logo=docker)](https://hub.docker.com/r/akougkas2030/zulipchat-mcp)
  [![License](https://img.shields.io/github/license/akougkas2030/zulipchat-mcp)](LICENSE)
  [![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
</div>

## 🚀 Installation

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

### Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (auto-installed by script)

## ⚡ Quick Start

1. **Install**
   ```bash
   uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
   ```

2. **Configure**
   ```bash
   export ZULIP_EMAIL="your-bot@zulip.com"
   export ZULIP_API_KEY="your-api-key" 
   export ZULIP_SITE="https://your-org.zulipchat.com"
   ```

3. **Run**  
   ```bash
   uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
   ```

That's it! Your MCP server is running and ready to connect to AI agents.

## 📋 Features

- 🔌 **MCP Compatible** - Works with Claude Desktop, Continue, Cursor, and other MCP clients
- ⚡ **Zero Dependencies** - No Docker, just Python + uv  
- 🔐 **Secure** - Multiple authentication methods, no hardcoded credentials
- 📨 **Full Zulip API** - Send messages, create streams, manage subscriptions  
- 📊 **Smart Analytics** - Daily summaries, activity reports, and catch-up features
- 🎯 **AI-Optimized** - Built-in prompts designed for AI workflows

### Available Tools

| Tool | Description |
|------|-------------|
| `send_message` | Send messages to streams or users |
| `get_messages` | Retrieve messages with filtering |
| `search_messages` | Search message content |
| `get_streams` | List available streams |
| `get_users` | List organization users |
| `add_reaction` | Add emoji reactions |
| `edit_message` | Edit existing messages |
| `get_daily_summary` | Generate activity reports |

### Available Resources

- `messages://stream_name` - Recent messages from specific streams
- `streams://all` - Complete streams directory
- `users://all` - Organization user directory

### Custom Prompts

- `summarize` - End-of-day summary with statistics
- `prepare` - Morning briefing with highlights
- `catch_up` - Quick summary of missed messages

## 🔧 Configuration

### Method 1: Environment Variables

```bash
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
```

### Method 2: Configuration File

Create `~/.config/zulipchat-mcp/config.json`:

```json
{
  "email": "your-bot@zulip.com",
  "api_key": "your-api-key",
  "site": "https://your-org.zulipchat.com"
}
```

### Method 3: Docker Secrets (Production)

```bash
# Create secrets
echo "your-api-key" | docker secret create zulip_api_key -
echo "your-bot@zulip.com" | docker secret create zulip_email -
echo "https://your-org.zulipchat.com" | docker secret create zulip_site -

# Use in docker-compose.yml
docker-compose up -d
```

## 🔑 Getting Your API Key

### Step 1: Log into your Zulip organization
Visit your Zulip organization (e.g., `https://your-org.zulipchat.com`)

### Step 2: Navigate to Settings
- Click your profile picture in the top right
- Select "Personal settings"

### Step 3: Generate API Key
- Go to the "Account & privacy" tab
- Scroll to "API key" section
- Click "Generate API key"
- Copy the key and your email

For detailed instructions with screenshots, see our [API Keys Guide](docs/api-keys.md).

## 🔌 MCP Client Configuration

### Claude Desktop

Add to your `claude_desktop_config.json`:

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

Add to your MCP configuration:

```json
{
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
```

### Cursor

Add to your Cursor MCP settings:

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

## 🛠️ Development

### Local Development

```bash
# Clone repository  
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Install dependencies
uv sync

# Run locally
uv run zulipchat-mcp
```

### Testing

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/zulipchat_mcp

# Type checking
uv run mypy src/
```

### Building & Distribution

```bash
# Build package
uv build

# Test locally with uvx
uvx --from . zulipchat-mcp
```

## 🌐 Platform Support

| Platform | Support | Method |
|----------|---------|---------|
| Linux | ✅ Native | `uvx + Python 3.10+` |
| macOS | ✅ Native | `uvx + Python 3.10+` |
| Windows | ✅ Native | `uvx + Python 3.10+` |

*No Docker required! Works anywhere Python runs.*

## 📖 Documentation

- [Setup Guide](docs/setup-guide.md) - Detailed installation instructions  
- [API Keys Guide](docs/api-keys.md) - How to get your Zulip API key
- [Commands Guide](docs/commands.md) - Available MCP tools and usage

## 🚨 Troubleshooting

### Common Issues

**Installation Failed**
```bash
# Check Python version
python3 --version  # Should be 3.10+

# Install/update uv manually
curl -LsSf https://astral.sh/uv/install.sh | sh

# Try installation again
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

**Connection Failed** 
```bash
# Test your credentials
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key" 
export ZULIP_SITE="https://your-org.zulipchat.com"

# Test configuration
uv run --with git+https://github.com/akougkas/zulipchat-mcp.git \
  python -c "from zulipchat_mcp.config import ConfigManager; print(ConfigManager().validate_config())"
```

**Permission Denied**
- Ensure your API key has necessary permissions
- Check your bot user has access to target streams
- Verify your Zulip site URL is correct

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

This project is built on the shoulders of amazing open source projects:

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io)** - The foundation that makes AI-to-service integration possible
- **[Zulip](https://zulip.com)** - Outstanding open source team chat platform with excellent API
- **[FastMCP](https://github.com/modelcontextprotocol/servers)** - Simplified MCP server framework
- **[uv](https://docs.astral.sh/uv/)** - Blazing fast Python package management from Astral
- **[Pydantic](https://pydantic.dev)** - Data validation and settings management using Python type annotations
- **[Docker](https://docker.com)** - Containerization platform enabling consistent deployments

Special thanks to the entire open source community that makes projects like this possible!

## 🔗 Related Projects

- [MCP Official Documentation](https://modelcontextprotocol.io)
- [Zulip API Documentation](https://zulip.com/api/)
- [Claude Desktop](https://claude.ai/desktop)

---

<div align="center">
  <sub>MIT Licensed • Community Driven • Open Source</sub>
</div>
