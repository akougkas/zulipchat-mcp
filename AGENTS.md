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

## Cleanup Plan (v2.5 follow-up)
- tools.commands: replace legacy import of `tools.search` with a v2.5 adaptor (use `advanced_search`) or remove the command if unused; add a smoke test.
- Scheduler surface: stop exporting non-existent names; either keep `services/scheduler.py` internal with corrected imports or defer public surface.
- Metrics: consolidate on `utils.metrics`; either façade or remove top-level `metrics.py` and update tests accordingly.
- Docs hygiene: move/remove `docs/v2.5.0/api-reference/streams.md.backup`.
- Optional: move `.claude/` to `.archived/claude/` or document as dev tooling.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `release:` (see `git log`).
- PRs should include: clear summary/motivation, linked issues, tests (or rationale), and example CLI invocation/output when relevant.
- Keep changes minimal and focused; update `README.md`/`AGENTS.md` when behavior or commands change.

## Security & Configuration Tips
- Do not commit secrets. Use `.env` (gitignored). Common vars: `ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`.
- Prefer CLI flags for credentials in MCP clients. For background features, `--enable-listener` is available.
- Optional checks before release: `uv run bandit -q -r src` and `uv run safety check`.
