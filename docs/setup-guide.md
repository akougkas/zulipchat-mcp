# ZulipChat MCP Setup Guide

This guide provides detailed instructions for setting up the ZulipChat MCP server on different platforms.

## Prerequisites

- Docker (recommended) or Python 3.10+
- Zulip organization access
- API key from your Zulip organization

## Installation Methods

### Method 1: Docker (Recommended)

Docker provides the easiest and most reliable installation method across all platforms.

#### Quick Start

```bash
# Pull the latest image
docker pull ghcr.io/akougkas/zulipchat-mcp:latest

# Run with environment variables
docker run -d \
  --name zulipchat-mcp \
  -e ZULIP_EMAIL="your-bot@zulip.com" \
  -e ZULIP_API_KEY="your-api-key" \
  -e ZULIP_SITE="https://your-org.zulipchat.com" \
  -p 3000:3000 \
  ghcr.io/akougkas/zulipchat-mcp:latest
```

#### Docker Compose

1. Create a `.env` file:
```bash
# Copy example configuration
cp .env.example .env

# Edit with your credentials
nano .env
```

2. Start the service:
```bash
docker-compose up -d
```

#### Docker Secrets (Production)

For production deployments, use Docker secrets:

```bash
# Create secrets
echo "your-api-key" | docker secret create zulip_api_key -
echo "your-bot@zulip.com" | docker secret create zulip_email -
echo "https://your-org.zulipchat.com" | docker secret create zulip_site -

# Deploy with secrets
docker stack deploy -c docker-compose.yml zulip-mcp
```

### Method 2: Native Python Installation

#### Using uv (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Install dependencies
uv pip install -e .

# Run the server
zulipchat-mcp server
```

#### Using pip

```bash
# Clone repository
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Run the server
zulipchat-mcp server
```

### Method 3: One-line Installation

```bash
curl -sSL https://raw.githubusercontent.com/akougkas/zulipchat-mcp/main/scripts/install.sh | bash
```

## Configuration

### Environment Variables

Set these environment variables before starting the server:

```bash
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
export MCP_PORT="3000"  # Optional, defaults to 3000
export MCP_DEBUG="false"  # Optional, defaults to false
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
# Install Docker (if not already installed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install and run
docker run -d --name zulipchat-mcp \
  -e ZULIP_EMAIL="..." \
  -e ZULIP_API_KEY="..." \
  -e ZULIP_SITE="..." \
  -p 3000:3000 \
  ghcr.io/akougkas/zulipchat-mcp:latest
```

### macOS

```bash
# Install Docker Desktop
brew install --cask docker

# Start Docker Desktop
open /Applications/Docker.app

# Install and run
docker run -d --name zulipchat-mcp \
  -e ZULIP_EMAIL="..." \
  -e ZULIP_API_KEY="..." \
  -e ZULIP_SITE="..." \
  -p 3000:3000 \
  ghcr.io/akougkas/zulipchat-mcp:latest
```

### Windows

#### Using Docker Desktop

1. Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)
2. Start Docker Desktop
3. Open PowerShell as Administrator:

```powershell
docker run -d --name zulipchat-mcp `
  -e ZULIP_EMAIL="your-bot@zulip.com" `
  -e ZULIP_API_KEY="your-api-key" `
  -e ZULIP_SITE="https://your-org.zulipchat.com" `
  -p 3000:3000 `
  ghcr.io/akougkas/zulipchat-mcp:latest
```

#### Using WSL2

```bash
# In WSL2 terminal
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Follow Linux instructions above
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

Add to your `.continue/config.json`:

```json
{
  "mcpServers": {
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
}
```

## Verification

### Test Configuration

```bash
# Test Docker installation
docker run --rm ghcr.io/akougkas/zulipchat-mcp:latest \
  python -c "from src.zulipchat_mcp import __version__; print(__version__)"

# Test connection with your credentials
docker run --rm \
  -e ZULIP_EMAIL="your-bot@zulip.com" \
  -e ZULIP_API_KEY="your-api-key" \
  -e ZULIP_SITE="https://your-org.zulipchat.com" \
  ghcr.io/akougkas/zulipchat-mcp:latest \
  python -c "from src.zulipchat_mcp.config import ConfigManager; ConfigManager().validate_config()"
```

### Check Server Status

```bash
# Check if container is running
docker ps

# View logs
docker logs zulipchat-mcp

# Check health
docker exec zulipchat-mcp python -c "from src.zulipchat_mcp.config import ConfigManager; print('✅ Healthy' if ConfigManager().validate_config() else '❌ Unhealthy')"
```

## Troubleshooting

### Common Issues

**Docker not found**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Permission denied**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Invalid credentials**
- Double-check your API key, email, and site URL
- Ensure the API key has necessary permissions
- Verify the site URL format (must include https://)

**Port already in use**
```bash
# Use different port
docker run -p 3001:3000 ghcr.io/akougkas/zulipchat-mcp:latest
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Environment variable
export MCP_DEBUG=true

# Or in Docker
docker run -e MCP_DEBUG=true ghcr.io/akougkas/zulipchat-mcp:latest
```

### Getting Help

1. Check the [troubleshooting section](../README.md#troubleshooting) in README
2. View [common issues](https://github.com/akougkas/zulipchat-mcp/issues) on GitHub
3. Create a new issue with:
   - Your platform (Linux/macOS/Windows)
   - Installation method used
   - Error messages (with sensitive info redacted)
   - Steps to reproduce