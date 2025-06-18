# ZulipChat MCP Server

<div align="center">
  <img src="https://akougkas.io/assets/logo.svg" alt="akougkas.io" width="120" />
  
  **Connect AI agents to Zulip Chat with ease**
  
  [![Docker](https://img.shields.io/docker/v/akougkas/zulipchat-mcp?label=docker)](https://hub.docker.com/r/akougkas/zulipchat-mcp)
  [![License](https://img.shields.io/github/license/akougkas/zulipchat-mcp)](LICENSE)
  [![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
</div>

## 🚀 Quick Start

### One-line Installation

```bash
curl -sSL https://raw.githubusercontent.com/akougkas/zulipchat-mcp/main/scripts/install.sh | bash
```

### Docker Compose

```yaml
version: '3.8'
services:
  zulipchat-mcp:
    image: ghcr.io/akougkas/zulipchat-mcp:latest
    environment:
      - ZULIP_EMAIL=${ZULIP_EMAIL}
      - ZULIP_API_KEY=${ZULIP_API_KEY}
      - ZULIP_SITE=${ZULIP_SITE}
    ports:
      - "3000:3000"
```

### Quick Docker Run

```bash
docker run -d \
  --name zulipchat-mcp \
  -e ZULIP_EMAIL="your-bot@zulip.com" \
  -e ZULIP_API_KEY="your-api-key" \
  -e ZULIP_SITE="https://your-org.zulipchat.com" \
  -p 3000:3000 \
  ghcr.io/akougkas/zulipchat-mcp:latest
```

## 📋 Features

- 🔌 **MCP Compatible** - Works with Claude Desktop, Continue, and other MCP clients
- 🐳 **Cross-Platform** - Runs on Linux, macOS, and Windows via Docker
- 🔐 **Secure** - Multiple authentication methods, no hardcoded credentials
- 📨 **Full Zulip API** - Send messages, create streams, manage subscriptions
- 📊 **Analytics** - Daily summaries, activity reports, and catch-up features
- 🎯 **Smart Prompts** - Built-in templates for team communication workflows

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
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/akougkas/zulipchat-mcp:latest"],
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
    "command": "zulipchat-mcp",
    "args": ["server"],
    "env": {
      "ZULIP_EMAIL": "your-bot@zulip.com",
      "ZULIP_API_KEY": "your-api-key",
      "ZULIP_SITE": "https://your-org.zulipchat.com"
    }
  }
}
```

## 🛠️ Development

### Local Installation

```bash
# Clone repository
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Running Tests

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src/zulipchat_mcp
```

### Building Docker Image

```bash
# Build locally
docker build -t zulipchat-mcp .

# Test the build
docker run --rm zulipchat-mcp python -c "from src.zulipchat_mcp import __version__; print(__version__)"
```

## 🌐 Platform Support

| Platform | Support | Installation Method |
|----------|---------|-------------------|
| Linux | ✅ Full | Docker, Native |
| macOS | ✅ Full | Docker, Native |
| Windows | ✅ Docker | Docker Desktop, WSL2 |

## 📖 Documentation

- [Setup Guide](docs/setup-guide.md) - Detailed installation instructions
- [API Keys Guide](docs/api-keys.md) - How to get your Zulip API key
- [Docker Hub](https://hub.docker.com/r/akougkas/zulipchat-mcp) - Container registry

## 🚨 Troubleshooting

### Common Issues

**Connection Failed**
```bash
# Check your credentials
docker run --rm -e ZULIP_SITE="..." -e ZULIP_EMAIL="..." -e ZULIP_API_KEY="..." \
  ghcr.io/akougkas/zulipchat-mcp:latest python -c \
  "from src.zulipchat_mcp.config import ConfigManager; ConfigManager().validate_config()"
```

**Permission Denied**
- Ensure your API key has the necessary permissions
- Check that your bot user has access to the streams you're trying to access

**Docker Issues**
```bash
# Check if container is running
docker ps

# View logs
docker logs zulipchat-mcp

# Restart container
docker restart zulipchat-mcp
```

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

## 🔗 Related Projects

- [MCP Official Documentation](https://modelcontextprotocol.io)
- [Zulip API Documentation](https://zulip.com/api/)
- [Claude Desktop](https://claude.ai/desktop)

---

<div align="center">
  Made with ❤️ by <a href="https://akougkas.io">akougkas.io</a>
</div>