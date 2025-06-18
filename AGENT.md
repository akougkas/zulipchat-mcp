# AI Agent Instructions for ZulipChat MCP

This document provides instructions for AI agents (Claude Desktop, Claude Code, etc.) on how to work with this repository.

## Quick Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/akougkas/zulipchat-mcp.git
   cd zulipchat-mcp
   ```

2. **Install with Docker (Recommended):**
   ```bash
   docker compose up -d
   ```

3. **Configure MCP client:**
   Add to your MCP configuration:
   ```json
   {
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
   ```

## Development Guidelines

### Code Structure
- `src/zulipchat_mcp/server.py` - Main MCP server implementation
- `src/zulipchat_mcp/client.py` - Zulip API client wrapper
- `src/zulipchat_mcp/config.py` - Configuration management

### Making Changes
When modifying this codebase:
1. Use parallel subagents when possible for faster development
2. Run tests before committing: `uv run pytest`
3. Update documentation if adding new features
4. Follow existing code style and patterns

### Testing
```bash
# Run unit tests
uv run pytest

# Test Docker build
docker build -t zulipchat-mcp:test .

# Test MCP server locally
uv run python -m src.zulipchat_mcp.server server
```

### Common Tasks

**Adding a new Zulip API method:**
1. Add method to `client.py`
2. Expose in MCP server in `server.py`
3. Add test in `tests/`
4. Update documentation

**Debugging:**
- Check Docker logs: `docker logs zulipchat-mcp`
- Enable debug mode: `export MCP_DEBUG=1`
- Test connection: `curl http://localhost:3000/health`

## Architecture Decisions

1. **Docker-first approach** - Ensures consistent cross-platform behavior
2. **Environment-based config** - Follows 12-factor app principles
3. **Minimal dependencies** - Only essential packages included
4. **Type hints throughout** - Better IDE support and error catching

## Release Process

1. Update version in `pyproject.toml`
2. Tag release: `git tag v1.0.0`
3. Push tags: `git push --tags`
4. GitHub Actions will build and publish Docker image