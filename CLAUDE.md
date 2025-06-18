# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ZulipChat MCP Server is a Model Context Protocol (MCP) server that enables AI agents to interact with Zulip Chat. It provides tools for sending messages, retrieving conversations, managing streams, and generating summaries through a FastMCP-based architecture.

## Development Commands

### Environment Setup
```bash
# Install with uv
uv sync

# Note: uv sync automatically installs dev dependencies if present
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/zulipchat_mcp

# Run specific test file
uv run pytest tests/test_server.py

# Run tests with verbose output
uv run pytest -v
```

### Code Quality
```bash
# Format code with Black
uv run black src/ tests/

# Lint with Ruff
uv run ruff check src/ tests/

# Type checking with mypy
uv run mypy src/zulipchat_mcp/
```

### Local Development
```bash
# Run MCP server locally for testing
uv run python -m src.zulipchat_mcp.server server

# Test configuration validation
uv run python -c "from src.zulipchat_mcp.config import ConfigManager; print('✅ Valid' if ConfigManager().validate_config() else '❌ Invalid')"
```

### Docker Operations
```bash
# Build Docker image
docker build -t zulipchat-mcp .

# Test Docker build
docker run --rm zulipchat-mcp python -c "from src.zulipchat_mcp import __version__; print(__version__)"

# Run with Docker Compose
docker-compose up -d

# View Docker logs
docker logs zulipchat-mcp
```

## Architecture Overview

### Core Components

**`src/zulipchat_mcp/server.py`** - Main MCP server implementation
- FastMCP-based server with 8 tools, 3 resources, and 3 custom prompts
- Global client management with lazy initialization
- Tools: `send_message`, `get_messages`, `search_messages`, `get_streams`, `get_users`, `add_reaction`, `edit_message`, `get_daily_summary`
- Resources: `messages://`, `streams://all`, `users://all`
- Prompts: `summarize`, `prepare`, `catch_up`

**`src/zulipchat_mcp/client.py`** - Zulip API wrapper
- Pydantic models: `ZulipMessage`, `ZulipStream`, `ZulipUser`
- Enhanced functionality: time-based filtering, daily summaries, advanced search
- Comprehensive error handling and data validation

**`src/zulipchat_mcp/config.py`** - Configuration management
- Multiple configuration sources with priority: env vars → Docker secrets → config files
- Robust validation: email format, API key length, URL validation
- Configuration locations: `~/.config/zulipchat-mcp/config.json`, `~/.zulipchat-mcp.json`, `./config.json`

### Key Dependencies
- **FastMCP**: MCP protocol implementation
- **Zulip**: Official Zulip Python client
- **Pydantic**: Data validation and modeling
- **pytest**: Testing framework with async support

## Configuration

### Environment Variables (Preferred)
```bash
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
```

### Docker Secrets (Production)
```bash
echo "your-api-key" | docker secret create zulip_api_key -
echo "your-bot@zulip.com" | docker secret create zulip_email -
echo "https://your-org.zulipchat.com" | docker secret create zulip_site -
```

### JSON Configuration Files
Create `~/.config/zulipchat-mcp/config.json`:
```json
{
  "email": "your-bot@zulip.com",
  "api_key": "your-api-key",
  "site": "https://your-org.zulipchat.com"
}
```

## Development Guidelines

### Adding New MCP Tools
1. Add tool function to `server.py` with proper `@mcp.tool()` decorator
2. Import and use `get_client()` for Zulip API access
3. Add corresponding method to `ZulipClientWrapper` in `client.py` if needed
4. Write tests in `tests/test_server.py`
5. Update documentation

### Adding New Zulip API Methods
1. Add method to `ZulipClientWrapper` class in `client.py`
2. Use appropriate Pydantic models for data validation
3. Handle errors gracefully with proper exception handling
4. Add unit tests with mocked Zulip client responses
5. Update type hints and docstrings

### Testing Strategy
- **Unit tests**: Mock Zulip client responses to test logic isolation
- **Integration tests**: Use `@pytest.mark.integration` for actual API calls
- **Configuration tests**: Test all configuration sources and validation
- **Model tests**: Verify Pydantic model serialization/deserialization

### Code Style Conventions
- **Line length**: 88 characters (Black default)
- **Type hints**: Required throughout codebase
- **Docstrings**: Use detailed docstrings for all public methods
- **Error handling**: Comprehensive exception handling with meaningful messages
- **Import organization**: Use Ruff for import sorting

## Production Considerations

### Security
- Never commit API keys or credentials
- Use environment variables or Docker secrets for sensitive data
- Validate all configuration inputs
- Implement proper error handling without exposing sensitive information

### Monitoring
- Use Docker health checks for containerized deployments
- Monitor API rate limits from Zulip
- Log configuration validation results
- Track MCP tool usage patterns

### Performance
- Client connection pooling handled by Zulip Python client
- Lazy initialization of global client in server.py
- Efficient message filtering with time-based queries
- Pydantic model optimization for large datasets