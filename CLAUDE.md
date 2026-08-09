# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current Status (v0.7.3-beta)

**Published**: [PyPI](https://pypi.org/project/zulipchat-mcp/) | [TestPyPI](https://test.pypi.org/project/zulipchat-mcp/)

Install: `uvx zulipchat-mcp --zulip-config-file ~/.zuliprc`

## Project Overview

ZulipChat MCP Server v0.7.3-beta - A Model Context Protocol (MCP) server that enables AI assistants to interact with Zulip Chat workspaces. The project uses FastMCP framework with DuckDB for persistence and async-first architecture.

## Essential Development Commands

### Environment Setup
```bash
# Install dependencies. Never use pip; this project uses uv.
uv sync

# Run the MCP server locally
uv run zulipchat-mcp --zulip-config-file ~/.zuliprc

# Quick run via uvx
uvx zulipchat-mcp
```

### Testing & Quality Assurance
```bash
# Run tests (60% coverage gate)
uv run pytest -q

# Skip slow/integration tests for faster feedback
uv run pytest -q -m "not slow and not integration"

# Full coverage report
uv run pytest --cov=src

# Linting and formatting
uv run ruff check .
changed_py=$(git diff --name-only -- '*.py')
[ -z "$changed_py" ] || uv run black --check $changed_py
uv run mypy src

# Security checks (optional)
uv run bandit -q -r src
uv run safety check
```

### Development Testing
```bash
# Test connection to Zulip (uses installed package; safe inside or outside the repo)
uv run python -c "from zulipchat_mcp.config import ConfigManager; from zulipchat_mcp.core.client import ZulipClientWrapper; c = ZulipClientWrapper(ConfigManager()); print('Connected:', c.identity_name)"

# Import validation
uv run python -c "from zulipchat_mcp.server import main; print('OK')"
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
- **Tools**: `src/zulipchat_mcp/tools/*.py` - MCP tool implementations
- **Configuration**: `src/zulipchat_mcp/config.py` - Environment/CLI configuration management
- **Database**: DuckDB integration for persistence and caching

### Dual Identity System
The client supports both user and bot credentials:
- User identity for reading/search operations
- Bot identity for posting messages and administrative tasks
- Identity switching via `switch_identity` tool

### Imports
Production code under `src/zulipchat_mcp/` uses package-relative imports:
```python
from .core.client import ZulipClientWrapper
from .tools.messaging import register_messaging_tools
```
Tests use `from src.zulipchat_mcp.*` because pytest runs with the repo root on `sys.path`. Never write `from src.zulipchat_mcp.*` inside `src/`.

## Tool Registration

Register tools through `tools/registration.py`, not bare `@mcp.tool`:
```python
from .registration import register_tool, optional_background_task

register_tool(
    mcp,
    my_tool_fn,
    name="my_tool",
    description="One-line, action-oriented.",
    task=optional_background_task(),  # only for long-running tools
)
```
Server-wide task advertisement is intentionally disabled in `server.py` (commit `70d3779`). Pass `task=optional_background_task()` only for genuinely long-running tools (e.g. `teleport_chat`, `wait_for_response`, `listen_events`). Normal fast tools omit `task=`.

## Tool Modes

- **Default**: 20 core tools registered via `register_core_tools(mcp)`.
- **Extended (60 tools)**: enable with `--extended-tools` flag or `ZULIPCHAT_EXTENDED_TOOLS=1` env var. Calls `register_extended_tools(mcp)`.

The split shipped in v0.6.0 to keep token overhead low for the common case.

## Development Guidelines

### Core Philosophy: Less is More
- **Elegant simplicity is the primary success metric**
- Achieve goals with minimal code - every line must justify its existence
- Prefer leveraging Zulip's native capabilities over custom implementations
- Remove complexity rather than managing it
- If a solution feels complicated, it probably is - find a simpler way

### Python Environment
- **Critical**: never use pip. Use `uv run` for all Python operations.
- Python 3.10+ required
- Use `uv add <package>` for dependencies, `uv sync` to synchronize

### Code Style
- Black formatting (line length 88)
- Ruff linting with pycodestyle, pyflakes, isort, bugbear, pyupgrade
- Type hints required for all public APIs
- Prefer async/await for I/O operations
- 4-space indentation, snake_case for functions/variables, CamelCase for classes
- **Minimize abstractions** - direct, clear code over clever patterns

### Testing Strategy
- Tests in `tests/` directory following pytest conventions
- Mark slow tests with `@pytest.mark.slow`, integration tests with `@pytest.mark.integration`
- Mock Zulip API calls to keep tests network-free
- 60% coverage gate enforced (`--cov-fail-under=60` in pyproject.toml)
- Use `uv run pytest` exclusively (no direct Python)

### File Operations
- **Always prefer editing existing files over creating new ones**
- **Consider deletion before addition** - can we solve this by removing code?
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
For Claude Code integration (tested syntax):
```bash
# From PyPI (once published)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx zulipchat-mcp

# From GitHub (available now)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp

# From TestPyPI (for testing)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zulipchat-mcp
```

**Important**: Use the `--` separator to properly pass uvx arguments to Claude Code. Environment variables must come before the `--` separator.

## Security Notes
- Never commit credentials to repository
- Use `.env` file (gitignored) for local development
- Administrative tools are not exposed to AI clients
- All credentials handled via environment variables or CLI arguments

## Server-Side LLM Analytics

### Server-Side LLM Provider (`src/zulipchat_mcp/core/llm.py`)
MCP sampling was removed in the 2026-07-28 stateless protocol. LLM-powered analytics tools call a server-side Anthropic provider directly:

```python
from zulipchat_mcp.core.llm import generate, LLMUnavailableError

# Direct server-side generation:
summary = await generate(prompt)
```

**Key Points:**
- Tools do **NOT** take a `Context` parameter (`ctx`).
- Server process requires `ANTHROPIC_API_KEY` for generation.
- Model override via `ANTHROPIC_MODEL` (defaults to `claude-opus-5`).
- Without `ANTHROPIC_API_KEY`, tools degrade gracefully returning `status="success"` with `llm_unavailable=True` and structured `data_summary`.

### Approved Emoji for Agent Reactions
Agents should use only these 12 emoji for consistency and quick responses:
- `thumbs_up`, `heart`, `rocket`, `fire`, `tada`, `check_mark`
- `warning`, `thinking`, `bulb`, `wrench`, `star`, `zap`

Invalid emoji (e.g., `thumbsup` without underscore) will fail at runtime. See `src/zulipchat_mcp/core/emoji_registry.py`.

### Agent-to-User Bidirectional Communication
Complete implementation exists at `src/zulipchat_mcp/tools/agents.py`:
- Agents can register stable profiles: `register_agent(agent_name, agent_type)`
- Agents can bind sessions to topics: `ensure_agent_session(agent_id, ...)`
- Agents can send messages: `agent_message(session_id, content, category=...)`
- Agents can request input: `request_user_input(session_id, question, options)`
- Agents can wait for responses: `wait_for_response(request_id)`
- Background MessageListener processes Zulip replies automatically
- Claude Code lifecycle hooks can be bridged via `zulipchat-mcp-hook`

### Command Chains (execute_chain)
Workflow automation with context passing between operations:
```python
execute_chain([
    {"type": "search_messages", "params": {"query_key": "search_query"}},
    {"type": "conditional_action", "params": {
        "condition": "len(context['search_results']) > 0",
        "true_action": {"type": "send_message", "params": {...}}
    }}
])
```

## Common Issues

### Coverage / cache contamination
Clean environment before major test runs:
```bash
rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache
uv sync --reinstall
```

### LLM Analytics Returns `llm_unavailable`
If analytics tools return `llm_unavailable=True`:
- Set `ANTHROPIC_API_KEY` in the environment of the `zulipchat-mcp` server process.
- Optional: set `ANTHROPIC_MODEL` to override the model.
- Calling agents can process the returned `data_summary` field directly when server-side LLM is unconfigured.

### DuckDB lock after unclean shutdown
Stale lock recovery shipped in commit `3db725a`. If you still hit "Database is locked by another process", check that no zombie `zulipchat-mcp` process holds the file in `.mcp/zulipchat/zulipchat.duckdb`.

## Project Skills (`.claude/skills/`)

Three project-specific skills extend the Zulip control plane. They activate when a Claude Code session is bound to a Zulip topic via `zulipchat-mcp-hook` and read `ZULIPCHAT_SESSION_ID`, `ZULIPCHAT_SESSION_STREAM`, `ZULIPCHAT_SESSION_TOPIC` from the shell:

- **`zulipchat-session-operator`**: treats Zulip as the owner control plane. Polls `poll_agent_events`, handles `/status`, `/pause`, `/resume`, `/cancel`, `/handoff`, enforces lifecycle-only posting discipline.
- **`zulipchat-loop`**: per-cycle policy for `/loop` runs. Each turn polls events, applies steering, emits at most one lifecycle message, does one unit of work.
- **`zulipchat-notifyme`**: explicit post into the bound topic with category (`message`/`started`/`blocked`/`waiting`/`completed`/`failed`).

If a session is not bound, these skills stop and explain rather than calling MCP tools blind.

## Release Process

Full checklist and rationale in [RELEASING.md](RELEASING.md). Key invariants:

- Tag must match `pyproject.toml` version exactly (`v0.7.1` ↔ `version = "0.7.1"`).
- Version must be in sync across `pyproject.toml`, `src/zulipchat_mcp/__init__.py`, `src/zulipchat_mcp/tools/system.py`, `server.json`, and release docs. Run `uv run python scripts/release_preflight.py --version X.Y.Z` to verify.
- `scripts/pre_release_smoke.sh` is a blocking gate. It installs the built wheel and starts the MCP stdio server with fake credentials, catching startup-only failures that `--version` cannot.
- FastMCP feature changes require real-registration tests and the MCP stdio smoke. Pay special attention to optional extras, `task` support, async task functions, and lifespan-managed services.
- GitHub release must be published, not draft. `publish.yml` only triggers on `published`.
- After publishing, verify: GitHub release shows "Latest", PyPI shows new version, `uvx --refresh-package zulipchat-mcp zulipchat-mcp --version` installs it.

## Open Source & Community Practices

This is a public open-source project. Follow these practices when handling community interactions:

### Responding to Issues
- Acknowledge new issues within 48 hours, even if just "Looking into this."
- Apply labels on triage: `bug`, `enhancement`, `good first issue`, `help wanted`, `needs-triage`, `community`, `dependencies`, `fastmcp`, `mcp-tools`, `breaking-change`.
- When closing, explain what was fixed and which version contains the fix.
- Credit the reporter in release notes.

### Responding to Pull Requests
- **Respond within 48 hours.** Silence kills contributor motivation.
- Prefer merging community PRs over reimplementing the same fix independently. Contributors get credit in their GitHub contribution graph.
- If changes are needed, request them on the PR — don't close and reimplement.
- If a fix was already applied independently, close the PR with explicit credit and acknowledgment. Explain what happened.
- Label community PRs with `community`.

### Release Notifications
- After publishing a release, comment on all issues fixed in that release.
- Mention the version number, what was fixed, and how to upgrade.
- Invite reporters to try the new version and provide feedback.
