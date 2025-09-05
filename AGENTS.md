# AGENTS.md

A simple, open format for guiding AI coding agents working with ZulipChat MCP Server.

## Project Overview

ZulipChat MCP Server is a Model Context Protocol (MCP) server that enables AI agents to interact with Zulip Chat. It provides tools for sending messages, retrieving conversations, managing streams, and generating summaries through a FastMCP-based architecture.

**Key Features:**
- **35+ MCP tools** for comprehensive Zulip and agent operations
- **Agent Communication System v1.4.0** - Bidirectional AI-Human communication
- **Multi-Instance Bot Identity** - Automatic project/session detection and routing
- **AFK Mode** - Smart notification control (only when away)
- **Personal Stream Organization** - One stream per agent type, topics per project
- **Claude Code Hooks Integration** - Automatic notifications from coding agents
- Task lifecycle management with progress tracking
- Stream organization and management tools
- Dual identity support (user + bot credentials)
- Project-aware notification routing
- Instance management across multiple machines
- UV-first deployment with cross-platform support
- **100% test pass rate** (257 tests, 75% code coverage)

## Development Environment

### Prerequisites
```bash
# Required: uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Python 3.10+ required
python --version  # Should be 3.10 or higher
```

### Initial Setup
```bash
# Clone and enter repository
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Install dependencies (creates virtual environment automatically)
uv sync

# Set up environment variables
cp .env.example .env  # Edit with your Zulip credentials

# Optional: Set up agent commands for your AI client
uv run agent_adapters/setup_agents.py all
```

### Environment Variables
```bash
# User credentials (required)
export ZULIP_EMAIL="your-email@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"

# Bot credentials (optional, for agent identity)
export ZULIP_BOT_EMAIL="claude-code-bot@zulip.com"
export ZULIP_BOT_API_KEY="bot-api-key"
export ZULIP_BOT_NAME="Claude Code"
```

## Build and Test Commands

### Testing
```bash
# Run all tests (257 tests total)
uv run pytest

# Run with coverage (currently at 75%)
uv run pytest --cov=src/zulipchat_mcp --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_server.py -v

# Run integration tests only
uv run pytest -m integration

# Clean test artifacts before commit
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
```

### Code Quality
```bash
# Format code (ALWAYS run before committing)
uv run black src/ tests/

# Lint code (fix issues before committing)
uv run ruff check src/ tests/ --fix

# Type checking (ensure no type errors)
uv run mypy src/zulipchat_mcp/
```

### Local Development
```bash
# Test configuration validity
uv run python -c "from src.zulipchat_mcp.config import ConfigManager; print('✅ Valid' if ConfigManager().validate_config() else '❌ Invalid')"

# Run MCP server locally
uv run zulipchat-mcp

# Test Zulip connection
uv run python -c "
from src.zulipchat_mcp.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
client = ZulipClientWrapper(ConfigManager())
streams = client.get_streams()
print(f'✅ Connected! Found {len(streams)} streams.')
"
```

### UV Operations
```bash
# Build package
uv build

# Test with uvx from local
uvx --from . zulipchat-mcp

# Test from GitHub directly
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
```

## Code Style Guidelines

### Python Standards
- **Line length**: 88 characters (Black default)
- **Quotes**: Double quotes for strings
- **Type hints**: Required for all public methods
- **Docstrings**: Required for all public functions/classes
- **Import order**: Sorted by Ruff (stdlib → third-party → local)

### Naming Conventions
- **Classes**: PascalCase (e.g., `ZulipClientWrapper`)
- **Functions/methods**: snake_case (e.g., `get_messages`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_TIMEOUT`)
- **Private methods**: Leading underscore (e.g., `_validate_input`)

### Error Handling
```python
# Always use specific exceptions
try:
    result = client.send_message(...)
except ValidationError as e:
    # Handle validation errors specifically
    return {"status": "error", "error": str(e)}
except ConnectionError as e:
    # Log sensitive errors, return safe message
    logger.error(f"Connection failed: {e}")
    return {"status": "error", "error": "Connection failed"}
```

## Project Structure

```
zulipchat-mcp/
├── src/zulipchat_mcp/
│   ├── __init__.py          # Version and metadata
│   ├── server.py            # MCP server with FastMCP (35+ tools, 3 resources, 3 prompts)
│   ├── client.py            # Zulip API wrapper with dual identity support
│   ├── config.py            # Multi-source configuration with bot credentials
│   ├── afk_state.py         # AFK mode management for notifications
│   ├── instance_identity.py # Multi-instance project/session detection
│   ├── database.py          # SQLite storage for agents and tasks
│   ├── models/
│   │   ├── agent.py         # Agent data models (Agent, InputRequest, etc.)
│   │   └── task.py          # Task lifecycle models (Task, TaskCompletion)
│   ├── services/
│   │   └── agent_registry.py # Agent registration and stream management
│   ├── tools/
│   │   ├── agent_communication.py  # Agent-to-human messaging
│   │   ├── task_tracking.py        # Task lifecycle management
│   │   └── stream_management.py    # Stream/topic organization
│   ├── assistants.py        # Intelligent assistant tools
│   ├── cache.py             # In-memory caching system with TTL
│   ├── commands.py          # Command chain system for workflow automation
│   ├── exceptions.py        # Custom exception hierarchy
│   ├── health.py            # Health monitoring and readiness checks
│   ├── logging_config.py    # Structured logging with context
│   ├── metrics.py           # Prometheus-style metrics collection
│   ├── notifications.py     # Smart notification system
│   ├── scheduler.py         # Native Zulip message scheduling
│   ├── security.py          # Input validation and rate limiting
│   └── async_client.py      # Async HTTP client for performance
├── tests/                   # Comprehensive test suite (257+ tests)
│   ├── test_server.py       # Server and MCP tool tests
│   ├── test_agent_system.py # Agent communication tests
│   ├── test_dual_identity.py # Bot identity tests
│   ├── test_assistants.py   # Assistant functionality tests
│   ├── test_commands.py     # Command chain tests
│   └── ...                  # Additional test modules
├── agent_adapters/          # Agent-specific setup utilities
│   └── setup_agents.py      # Command definitions including AFK
├── docs/                    # User documentation and guides
│   └── BOT_SETUP.md         # Bot identity setup guide
├── pyproject.toml           # UV-based project configuration
├── CHANGELOG.md             # Detailed version history
├── AGENTS.md                # This file - AI agent guidelines
└── install.sh               # UV-based installation script
```

## Adding New Features

### Adding a New MCP Tool
1. Add tool function to `server.py` with `@mcp.tool()` decorator
2. Use `get_client()` for Zulip API access
3. Add corresponding method to `ZulipClientWrapper` if needed
4. Write tests in `tests/test_server.py`
5. Update README.md documentation

### Example Tool Implementation
```python
@mcp.tool()
def new_tool(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    """Tool description for MCP clients.
    
    Args:
        param1: Description of param1
        param2: Optional parameter with default
    """
    try:
        # Input validation
        if not validate_input(param1):
            raise ValidationError("Invalid input")
        
        # Get client and perform operation
        client = get_client()
        result = client.perform_operation(param1, param2)
        
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {"status": "error", "error": "Operation failed"}
```

## Testing Guidelines

### Test Categories
- **Unit tests**: Mock external dependencies
- **Integration tests**: Mark with `@pytest.mark.integration`
- **Configuration tests**: Test all config sources
- **Model tests**: Validate Pydantic models

### Running Specific Test Categories
```bash
# Unit tests only
uv run pytest -m "not integration"

# Integration tests only
uv run pytest -m integration

# Failed tests from last run
uv run pytest --lf
```

## PR Guidelines

### Before Submitting
1. **Format code**: `uv run black src/ tests/`
2. **Fix linting**: `uv run ruff check src/ tests/ --fix`
3. **Type check**: `uv run mypy src/zulipchat_mcp/`
4. **Run tests**: `uv run pytest`
5. **Update docs**: Ensure README.md is current

### Commit Message Format
```
type: brief description

- Detailed change 1
- Detailed change 2

Fixes #issue_number
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Template
```markdown
## Summary
Brief description of changes

## Changes
- [ ] Change 1
- [ ] Change 2

## Testing
- [ ] All tests pass
- [ ] Added new tests for changes
- [ ] Manual testing completed

## Documentation
- [ ] Updated README.md if needed
- [ ] Updated AGENTS.md if needed
```

## Security Considerations

### Never Commit
- API keys or tokens
- Passwords or secrets
- `.env` files with real credentials
- Personal configuration files

### Input Validation
- Always sanitize user inputs
- Validate message content length
- Check stream/user names for injection
- Use parameterized queries

### Error Handling
- Never expose internal errors to users
- Log sensitive errors privately
- Return generic error messages
- Include request IDs for debugging

## Performance Considerations

### Optimization Guidelines
- Use lazy initialization for clients
- Implement caching for repeated queries
- Batch API calls when possible
- Use async operations for I/O

### Resource Management
```python
# Use context managers for resources
async with get_async_client() as client:
    result = await client.operation()

# Clean up on shutdown
async def shutdown_handler():
    if zulip_client:
        await zulip_client.close()
```

## Debugging Tips

### Common Issues

1. **"No Zulip email found"**
```bash
# Check environment variables
echo $ZULIP_EMAIL
# Re-export from .env
export $(cat .env | grep -v '^#' | xargs)
```

2. **Connection failures**
```bash
# Test connection directly
uv run python -c "
from src.zulipchat_mcp.config import ConfigManager
ConfigManager().validate_config()
"
```

3. **MCP client not connecting**
- Check absolute paths in config
- Verify uv is in PATH
- Restart MCP client after changes

### Debug Logging
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
export MCP_DEBUG=true
```

## Monorepo Considerations

For subprojects, create nested AGENTS.md files:
```
zulipchat-mcp/
├── AGENTS.md              # Main project
├── agents/
│   └── AGENTS.md         # Agent-specific guidelines
└── extensions/
    └── AGENTS.md         # Extension-specific guidelines
```

Nested files inherit from parent but can override specific sections.

## AI Agent Specific Notes

### For Code Generation
- Follow existing patterns in the codebase
- Use type hints consistently
- Include comprehensive error handling
- Add tests for new functionality

### For Code Review
- Check for security vulnerabilities
- Verify error handling completeness
- Ensure consistent code style
- Validate test coverage

### For Documentation
- Update relevant .md files
- Keep examples current
- Document breaking changes
- Include migration guides

## Links and Resources

- [Project Repository](https://github.com/akougkas/zulipchat-mcp)
- [MCP Documentation](https://modelcontextprotocol.io)
- [Zulip API Reference](https://zulip.com/api/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Issues & Support](https://github.com/akougkas/zulipchat-mcp/issues)

---
*This AGENTS.md follows the open standard at [agents.md](https://agents.md) for AI coding assistants.*