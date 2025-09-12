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
- `uv run pytest -q` — run tests. Use `-m "not slow and not integration"` to skip long tests; `--cov=src` for coverage.
- `uv run ruff check .` — lint; `uv run black .` — format; `uv run mypy src` — type-check.

## Coding Style & Naming Conventions
- Python 3.10+, 4‑space indent, Black line length 88, Ruff configured (pycodestyle, pyflakes, isort, bugbear, pyupgrade). Keep imports sorted.
- Names: functions/variables `snake_case`, classes `CamelCase`, constants `UPPER_SNAKE_CASE`, modules `lower_snake_case.py`.
- Tool groups should expose `register_*_tools(mcp)` mirroring patterns in `src/zulipchat_mcp/tools/`.

## Testing Guidelines
- Place tests under `tests/` as `test_*.py`; classes `Test*`, functions `test_*`.
- Mark long/external tests with `@pytest.mark.slow` or `@pytest.mark.integration` and gate in CI via markers.
- Prefer fast, deterministic unit tests; mock Zulip API calls. Aim for meaningful coverage with `pytest --cov=src`.
- Testing strategy: always use `uv` (no direct Python invocations), keep tests isolated and network-free by mocking clients, aggressively clean caches/venv before major coverage pushes (`rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* && uv sync --reinstall`), raise the coverage gate incrementally (e.g., 40% → 60% → 75% → 90%+) while adding minimal, targeted tests without altering functionality.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `release:` (see `git log`).
- PRs should include: clear summary/motivation, linked issues, tests (or rationale), and example CLI invocation/output when relevant.
- Keep changes minimal and focused; update `README.md`/`AGENTS.md` when behavior or commands change.

## Security & Configuration Tips
- Do not commit secrets. Use `.env` (gitignored). Common vars: `ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`.
- Prefer CLI flags for credentials in MCP clients. For background features, `--enable-listener` is available.
- Optional checks before release: `uv run bandit -q -r src` and `uv run safety check`.
