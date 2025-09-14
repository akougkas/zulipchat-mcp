# Repository Guidelines

## Project Structure & Module Organization
- Source code lives in `src/zulipchat_mcp/`:
  - `tools/` (tool groups), `core/` (client, cache, commands), `services/` (listener, scheduler), `integrations/` (client installers), `utils/` (logging, metrics, db).
- Tests are in `tests/` (pytest with `slow` and `integration` markers).
- Config via CLI flags or environment; copy `.env.example` to `.env` for local dev. Entry points: `zulipchat-mcp`, `zulipchat-mcp-integrate`.

## Build, Test, and Development Commands
- `uv sync` — install dependencies.
- `uv run zulipchat-mcp --zulip-email ... --zulip-api-key ... --zulip-site ... [--enable-listener]` — run server locally.
- `uvx zulipchat-mcp` — quick run via uvx shim.
- `uv run pytest -q` — run tests. Use `-m "not slow and not integration"` to skip long tests; `--cov=src` for coverage. Gate is set to 90%.
- `uv run ruff check .` — lint; `uv run black .` — format; `uv run mypy src` — type-check.

## Coding Style & Naming Conventions
- Python 3.10+, 4‑space indent, Black line length 88, Ruff configured (pycodestyle, pyflakes, isort, bugbear, pyupgrade). Keep imports sorted.
- Names: functions/variables `snake_case`, classes `CamelCase`, constants `UPPER_SNAKE_CASE`, modules `lower_snake_case.py`.
- Tool groups should expose `register_*_tools(mcp)` mirroring patterns in `src/zulipchat_mcp/tools/`.

## Testing Guidelines
- Place tests under `tests/` as `test_*.py`; classes `Test*`, functions `test_*`.
- Mark long/external tests with `@pytest.mark.slow` or `@pytest.mark.integration` and gate in CI via markers.
- Prefer fast, deterministic unit tests; mock Zulip API calls. Aim for meaningful coverage with `pytest --cov=src`.
- Testing strategy: always use `uv` (no direct Python invocations), keep tests isolated and network-free by mocking clients, aggressively clean caches/venv before major coverage pushes (`rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache && uv sync --reinstall`), and maintain the coverage gate at 90% while adding minimal, targeted tests without altering functionality.

- Note on contract-only runs: Running only the tests matching `-k "contract_"` will likely trip the global coverage gate; use the full suite for verification, or append `--no-cov` when exploring locally (e.g., `uv run pytest -q -k "contract_" --no-cov`).


## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `release:` (see `git log`).
- PRs should include: clear summary/motivation, linked issues, tests (or rationale), and example CLI invocation/output when relevant.
- Keep changes minimal and focused; update `README.md`/`AGENTS.md` when behavior or commands change.

## Distribution & Installation Testing
- **Installation Methods**: Three primary distribution channels:
  - `uvx zulipchat-mcp` (PyPI - fastest, pre-built wheels)
  - `uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp` (GitHub - builds from source)
  - `uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zulipchat-mcp` (TestPyPI - for pre-release testing)
- **Credential Loading**: Enhanced `.env` file support checks both current directory and home directory (~/.env). Priority: CLI args > current directory .env > home directory .env > environment variables.
- **Claude Code Integration**: Use `--` separator for proper argument passing:
  ```bash
  # Correct syntax (tested)
  claude mcp add zulipchat -e ZULIP_EMAIL=bot@org.com -e ZULIP_API_KEY=key -e ZULIP_SITE=https://org.zulipchat.com -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
  ```
- **Testing Before Release**: Always test all three installation methods with real credentials in clean environments to ensure packaging works correctly.

## Security & Configuration Tips
- Do not commit secrets. Use `.env` (gitignored). Common vars: `ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`.
- Prefer CLI flags for credentials in MCP clients. For background features, `--enable-listener` is available.
- Optional checks before release: `uv run bandit -q -r src` and `uv run safety check`.

## Documentation Resources

### User Documentation
- [Installation Guide](docs/user-guide/installation.md) - Detailed setup instructions
- [Quick Start Tutorial](docs/user-guide/quick-start.md) - Get running quickly
- [Configuration Reference](docs/user-guide/configuration.md) - All configuration options
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

### Developer Documentation
- [Architecture Overview](docs/developer-guide/architecture.md) - System design and components
- [Tool Categories](docs/developer-guide/tool-categories.md) - Tool organization patterns
- [Foundation Components](docs/developer-guide/foundation-components.md) - Core building blocks
- [Testing Guide](docs/testing/README.md) - Testing strategies and coverage requirements

### API Reference
- [Messaging Tools](docs/api-reference/messaging.md) - Message operations
- [Stream Tools](docs/api-reference/streams.md) - Stream management
- [Event Tools](docs/api-reference/events.md) - Real-time events
- [User Tools](docs/api-reference/users.md) - User management
- [Search Tools](docs/api-reference/search.md) - Search and analytics
- [File Tools](docs/api-reference/files.md) - File operations

### Release Documentation
- [Current Release (v2.5.0)](docs/releases/v2.5.0/RELEASE_v2.5.0.md)
- [Full Documentation Index](docs/README.md)
