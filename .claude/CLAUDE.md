# Zulip Chat MCP Development System

A streamlined AI-powered development environment optimized for building and maintaining the Zulip Chat Model Context Protocol server.

## Project Overview

Building a production-ready MCP server that bridges Claude/AI assistants with Zulip chat, enabling intelligent conversation management, message processing, and team collaboration features.

## Development Guidelines

### Python Environment
- **ALWAYS** use `uv run` for Python operations (never use pip directly)
- Use `uv add <package>` to install dependencies
- Use `uv sync` to synchronize environment
- Maintain `pyproject.toml` as single source of truth

### MCP Protocol Standards
- Follow official MCP specification for all tool implementations
- Ensure proper error handling and schema validation
- Implement comprehensive logging for debugging
- Use async/await patterns for all I/O operations

### Zulip API Best Practices
- Implement rate limiting and backoff strategies
- Cache frequently accessed data (streams, users)
- Use bulk operations where available
- Handle authentication securely via environment variables

## Agent-First Development

### Intelligent Task Delegation
Our optimized agent team uses compute efficiently:
- **Opus (High Reasoning)**: orchestrator, code-architect, debugger
- **Sonnet (Balanced)**: code-writer, test-implementer  
- **Haiku (Fast Execution)**: api-researcher, pattern-analyzer

### Workflow Patterns
1. **Research Phase**: Launch lightweight agents in parallel
2. **Design Phase**: Engage architect for system design
3. **Implementation**: Sequential code writing and testing
4. **Validation**: Debug and optimize

## Quick Commands

### Zulip MCP Workflows
- `/zulip-tool "Create new MCP tool"` - Scaffold new tool with tests
- `/zulip-test` - Run comprehensive test suite
- `/zulip-debug "Error message"` - Debug MCP server issues
- `/mcp-validate` - Validate MCP protocol compliance

### Development Commands
- `/agents` - View available specialized agents
- `/test` - Run project tests with coverage
- `/lint` - Check code quality and formatting

## Project Structure

```
zulipchat-mcp/
├── src/zulipchat_mcp/
│   ├── server.py          # Main MCP server
│   ├── handlers/           # Tool implementations
│   ├── models/            # Pydantic models
│   ├── utils/             # Shared utilities
│   └── integrations/      # Client integrations
├── tests/                 # Comprehensive test suite
├── .claude/              # AI agent configurations
│   ├── agents/           # Specialized subagents
│   ├── commands/         # Workflow commands
│   └── workflows/        # Automation scripts
└── pyproject.toml        # Project configuration
```

## Core Features

### Implemented Tools
- Message operations (send, search, update, delete)
- Stream management (list, subscribe, create)
- User interactions (presence, profiles, mentions)
- File handling (upload, download, attachments)

### Quality Standards
- Type hints for all functions (100% coverage)
- Comprehensive error handling with custom exceptions
- Async-first architecture for performance
- Full test coverage (unit, integration, e2e)

## Testing Strategy

### Test Execution
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/zulipchat_mcp

# Run specific test category
uv run pytest tests/test_handlers/
```

### Test Categories
- **Unit Tests**: Individual function validation
- **Integration Tests**: Zulip API interaction
- **MCP Protocol Tests**: Schema compliance
- **E2E Tests**: Full server functionality

## Development Workflow

1. **Feature Request**: Use orchestrator to plan implementation
2. **Research**: api-researcher fetches Zulip/MCP documentation
3. **Design**: code-architect creates technical specification
4. **Implementation**: code-writer produces production code
5. **Testing**: test-implementer ensures quality
6. **Debugging**: debugger resolves any issues

## Important Reminders

- **NEVER** create files unless necessary - prefer editing
- **ALWAYS** validate against MCP specification
- **VERIFY** Zulip API responses and handle errors
- **DOCUMENT** architectural decisions in code
- **TEST** every new feature comprehensively

## Environment Variables

Required for operation:
```bash
ZULIP_EMAIL=bot@example.com
ZULIP_API_KEY=your-api-key
ZULIP_SITE=https://your-domain.zulipchat.com
```

## Quick Links

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Zulip API Documentation](https://zulip.com/api/)
- [Project Repository](https://github.com/user/zulipchat-mcp)