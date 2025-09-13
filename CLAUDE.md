# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ZulipChat MCP Server v2.5.0 - A Model Context Protocol (MCP) server that enables AI assistants to interact with Zulip Chat workspaces. The project uses FastMCP framework with DuckDB for persistence and async-first architecture.

## Essential Development Commands

### Environment Setup
```bash
# Install dependencies (NEVER use pip - always use uv)
uv sync

# Run the MCP server locally
uv run zulipchat-mcp --zulip-email your@email.com --zulip-api-key YOUR_KEY --zulip-site https://yourorg.zulipchat.com

# Quick run via uvx
uvx zulipchat-mcp
```

### Testing & Quality Assurance
```bash
# Run tests (90% coverage gate enforced)
uv run pytest -q

# Skip slow/integration tests for faster feedback
uv run pytest -q -m "not slow and not integration"

# Full coverage report
uv run pytest --cov=src

# Linting and formatting
uv run ruff check .
uv run black .
uv run mypy src

# Security checks (optional)
uv run bandit -q -r src
uv run safety check
```

### Development Testing
```bash
# Test connection to Zulip
uv run python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
print(f'Connected! Identity: {client.identity_name}')
"

# Import validation
uv run python -c "from src.zulipchat_mcp.server import main; print('OK')"
```

## Architecture Overview

### Core Structure
```
src/zulipchat_mcp/
├── core/           # Business logic (client, identity, commands, batch processing)
├── tools/          # MCP tool implementations (messaging, streams, search, events, users, files)
├── utils/          # Shared utilities (logging, database, health, metrics)
├── services/       # Background services (scheduler, message listener)
├── integrations/   # AI client integrations
└── config.py       # Configuration management
```

### Key Components

- **Entry Point**: `src/zulipchat_mcp/server.py` - Main MCP server with CLI argument parsing
- **Client Wrapper**: `src/zulipchat_mcp/core/client.py` - Dual identity Zulip API wrapper with caching
- **Tools**: `src/zulipchat_mcp/tools/*_v25.py` - MCP tool implementations following v2.5 patterns
- **Configuration**: `src/zulipchat_mcp/config.py` - Environment/CLI configuration management
- **Database**: DuckDB integration for persistence and caching

### Dual Identity System
The client supports both user and bot credentials:
- User identity for reading/search operations
- Bot identity for posting messages and administrative tasks
- Identity switching via `switch_identity` tool

### Import Patterns (v2.5)
All imports follow the new modular structure:
```python
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.tools.messaging_v25 import register_messaging_v25_tools
```

**Important**: The codebase underwent complete v2.5 architectural refactor. Previous flat imports like `from zulipchat_mcp.client import` are deprecated.

## Tool Registration Pattern

Each tool module exports a registration function:
```python
# Pattern used across all v2.5 tool modules
def register_*_v25_tools(mcp: FastMCP) -> None:
    """Register tools with the MCP server."""
    # Tool implementations here
```

## Development Guidelines

### Python Environment
- **Critical**: NEVER use pip - always use `uv run` for all Python operations
- Python 3.10+ required
- Use `uv add <package>` for dependencies, `uv sync` to synchronize

### Code Style
- Black formatting (line length 88)
- Ruff linting with pycodestyle, pyflakes, isort, bugbear, pyupgrade
- Type hints required for all public APIs
- Prefer async/await for I/O operations
- 4-space indentation, snake_case for functions/variables, CamelCase for classes

### Testing Strategy
- Tests in `tests/` directory following pytest conventions
- Mark slow tests with `@pytest.mark.slow`, integration tests with `@pytest.mark.integration`
- Mock Zulip API calls to keep tests network-free
- 90% coverage requirement enforced
- Use `uv run pytest` exclusively (no direct Python)

### File Operations
- **Always prefer editing existing files over creating new ones**
- Use Read tool before any file modifications
- Maintain existing code patterns and conventions

## Configuration

### Environment Variables
```bash
ZULIP_EMAIL=your@email.com
ZULIP_API_KEY=your_api_key
ZULIP_SITE=https://yourorg.zulipchat.com
ZULIP_BOT_EMAIL=bot@yourorg.zulipchat.com  # Optional
ZULIP_BOT_API_KEY=bot_api_key              # Optional
```

### CLI Integration
For Claude Code integration:
```bash
claude mcp add zulipchat uv run zulipchat-mcp
```

## Security Notes
- Never commit credentials to repository
- Use `.env` file (gitignored) for local development
- Administrative tools removed from AI access in v2.5 for security
- All credentials handled via environment variables or CLI arguments

## Common Issues

### Import Errors
Ensure using v2.5 import paths:
```python
# Correct (v2.5)
from src.zulipchat_mcp.core.client import ZulipClientWrapper

# Incorrect (legacy)
from zulipchat_mcp.client import ZulipClientWrapper
```

### Coverage Issues
Clean environment before major test runs:
```bash
rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache
uv sync --reinstall
```

### Connection Testing
Always test Zulip connection with provided test snippet before implementing features.