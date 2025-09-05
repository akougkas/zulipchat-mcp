# AGENTS.md

A simple, open format for guiding AI coding agents working with ZulipChat MCP Server.

## Project Overview

ZulipChat MCP Server is a Model Context Protocol (MCP) server that enables AI agents to interact with Zulip Chat. It provides tools for sending messages, retrieving conversations, managing streams, and generating summaries through a FastMCP-based architecture.

**Key Features:**
- 8 MCP tools for comprehensive Zulip operations
- 3 MCP resources for data access (messages, streams, users)
- 3 custom prompts for summaries and reports
- Multiple configuration methods (env vars, Docker secrets, config files)
- Docker-first deployment with Alpine Linux

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
```

### Environment Variables
```bash
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
```

## Build and Test Commands

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/zulipchat_mcp

# Run specific test file
uv run pytest tests/test_server.py -v

# Run integration tests only
uv run pytest -m integration
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
uv run python -m src.zulipchat_mcp.server server

# Test Zulip connection
uv run python -c "
from src.zulipchat_mcp.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
client = ZulipClientWrapper(ConfigManager())
streams = client.get_streams()
print(f'✅ Connected! Found {len(streams)} streams.')
"
```

### Docker Operations
```bash
# Build Docker image
docker build -t zulipchat-mcp .

# Run with Docker
docker run -it --rm \
  -e ZULIP_EMAIL="$ZULIP_EMAIL" \
  -e ZULIP_API_KEY="$ZULIP_API_KEY" \
  -e ZULIP_SITE="$ZULIP_SITE" \
  zulipchat-mcp

# Use Docker Compose
docker-compose up -d
docker logs -f zulipchat-mcp
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
│   ├── __init__.py        # Version and metadata
│   ├── server.py          # MCP server with FastMCP (8 tools, 3 resources)
│   ├── client.py          # Zulip API wrapper with Pydantic models
│   └── config.py          # Multi-source configuration management
├── tests/
│   ├── test_server.py     # Unit and integration tests
│   └── __init__.py
├── agents/                # AI agent specific implementations
├── docs/                  # User documentation
├── scripts/               # Installation and utility scripts
├── slash_commands.py      # Universal slash commands
├── pyproject.toml         # Project configuration
├── Dockerfile            # Multi-stage Alpine build
└── docker-compose.yml    # Docker Compose configuration
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