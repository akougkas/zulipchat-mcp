# Contributing to ZulipChat MCP

Thanks for your interest in contributing! This project welcomes first‑time contributors and experienced folks alike. We strive to keep the process friendly, clear, and efficient so you can make an impact quickly.

## Our Values & Code of Conduct

- Be respectful, inclusive, and collaborative.
- Assume positive intent and prefer constructive feedback.
- Zero tolerance for harassment or discrimination.

We adopt the spirit of the Contributor Covenant. If you experience or witness unacceptable behavior, please open an issue labeled "conduct" or contact the maintainers via GitHub.

---

## Ways You Can Contribute

- Report bugs and edge cases
- Propose enhancements or new tools
- Improve documentation and examples
- Add tests and refactor for clarity
- Help with issue triage and review

Start by browsing open issues. Good entry points are often labeled "good first issue" or "help wanted" (if present).

---

## Quick Start (Development)

Prerequisites:

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) installed (we use uv for everything)

Setup:

```bash
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync

# Optional: local env (never commit secrets)
cp -n .env.example .env || true

# Run the MCP server locally (example; requires credentials)
uv run zulipchat-mcp --zulip-email your@email.com \
  --zulip-api-key YOUR_KEY \
  --zulip-site https://yourorg.zulipchat.com
```

Helpful docs:

- README: `README.md`
- Development guidelines for agents/tools: `AGENTS.md`
- Claude Code specifics: `CLAUDE.md`
- Testing documentation: `docs/testing/README.md`
- API reference: `docs/api-reference/`
- Troubleshooting guide: `docs/TROUBLESHOOTING.md`

Security & configuration:

- Do not commit secrets. Use `.env` (gitignored) or CLI flags.
- Prefer CLI flags in MCP clients. Background features support `--enable-listener`.

---

## Project Structure (What to Edit Where)

```text
src/zulipchat_mcp/
├── core/           # Client, cache, commands
├── tools/          # MCP tool groups (messaging, streams, search, events, users, files)
├── services/       # Background services (listener, scheduler)
├── integrations/   # Client installers (Claude Code, Cursor, etc.)
├── utils/          # Logging, metrics, database
└── config.py       # Configuration management
```

Tool group pattern (v0.4):

- New tools live under `src/zulipchat_mcp/tools/`
- Expose a registration function like `register_*_tools(mcp)` that mirrors existing modules
- Follow v0.4 import style (no legacy flat imports):

```python
from src.zulipchat_mcp.core.client import ZulipClientWrapper
```

---

## Development Standards

Run these before you push:

```bash
uv run pytest -q                       # tests (90% coverage gate in CI)
uv run ruff check .                    # lint
uv run black .                         # format (line length 88)
uv run mypy src                        # type-check
```

Recommended (optional) security checks:

```bash
uv run bandit -q -r src
uv run safety check
```

Style & conventions:

- Python 3.10+, 4-space indentation
- Black (line length 88), Ruff (pycodestyle, pyflakes, isort, bugbear, pyupgrade)
- Names: functions/variables `snake_case`, classes `CamelCase`, constants `UPPER_SNAKE_CASE`, modules `lower_snake_case.py`
- Public APIs should be type-annotated
- Prefer async for I/O; use guard clauses and clear error handling
- Keep imports sorted; avoid deep nesting

Testing guidelines:

- Put tests under `tests/` as `test_*.py` (classes `Test*`, functions `test_*`)
- Mock Zulip API calls; keep tests deterministic and network-free
- Use markers to scope local runs:

```bash
uv run pytest -q -m "not slow and not integration"
```

- Note: Running only contract tests like `-k "contract_"` can trip the global coverage gate. When exploring locally, use `--no-cov`:

```bash
uv run pytest -q -k "contract_" --no-cov
```

- Before big coverage pushes, a clean slate helps:

```bash
rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache
uv sync --reinstall
```

---

## Git Workflow

1. Create a feature branch from `main`:
   - Suggested naming: `type/scope-short-description` (e.g., `feat/search-aggregations`)
2. Use Conventional Commits for messages:
   - `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `perf:`, `ci:`, `build:`, `release:`
3. Keep PRs focused and reasonably small. Large refactors should be split and discussed first.
4. Update docs when behavior or commands change (`README.md`, `AGENTS.md`, `CLAUDE.md`).
5. Avoid breakages in public APIs; if unavoidable, call out clearly as breaking change.

---

## Pull Request Checklist

Before requesting review, please ensure:

- [ ] Title uses Conventional Commits style
- [ ] PR description explains motivation, approach, and alternatives considered
- [ ] Linked issue (if applicable)
- [ ] Tests added/updated; suite passes locally via `uv run pytest -q`
- [ ] Lint, format, and type-check pass (`ruff`, `black`, `mypy`)
- [ ] No secrets, keys, or credentials in code, tests, or commit history
- [ ] Docs updated if behavior, CLI flags, or tool APIs changed (`README.md`, `AGENTS.md`, `CLAUDE.md`)
- [ ] Example CLI invocation/output included when relevant
- [ ] For tools: follows v0.4 registration pattern under `src/zulipchat_mcp/tools/`

Review & merge:

- Maintainers review for clarity, correctness, tests, and alignment with project scope
- We generally use squash-and-merge to keep history clean

---

## Releases (FYI)

Only maintainers can publish releases. Community PRs are welcome and will be included in the next release as appropriate. We follow Semantic Versioning (MAJOR.MINOR.PATCH). See release documentation in `docs/releases/` for version history.

If you propose a change that affects user-visible behavior, please add a short "Proposed change note" in your PR description to help with release notes.

---

## Documentation Updates

When adding features or changing behavior, consider whether any of the following should be updated:

- `README.md` (features, installation, integration examples)
- `AGENTS.md` (repository guidelines, dev commands)
- `CLAUDE.md` (Claude Code usage and command syntax)
- `docs/api-reference/` (API documentation for tools)
- `docs/user-guide/` (user-facing documentation)
- `docs/developer-guide/` (architecture and development docs)
- `docs/TROUBLESHOOTING.md` (common issues and solutions)

---

## Local Command Reference (Cheat Sheet)

```bash
# Install deps
uv sync

# Run server (requires credentials)
uv run zulipchat-mcp --zulip-email ... --zulip-api-key ... --zulip-site ... [--enable-listener]

# Tests (fast)
uv run pytest -q -m "not slow and not integration"

# Full checks
uv run pytest -q && uv run ruff check . && uv run black . && uv run mypy src

# Optional security
uv run bandit -q -r src && uv run safety check
```

---

## License

By contributing, you agree that your contributions will be licensed under the project’s MIT License.

---

## Questions?

If anything is unclear, please open an issue. We’re happy to help you get started. Thank you for contributing!
