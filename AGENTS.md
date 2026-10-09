# Repository Guidelines

## Current Status (v0.7.5)

**Current release**: v0.7.5 on [PyPI](https://pypi.org/project/zulipchat-mcp/). Install: `uvx zulipchat-mcp`.

## Project Structure & Module Organization
- Source code lives in `src/zulipchat_mcp/`:
  - `tools/` (tool groups), `core/` (client, cache, commands), `services/` (listener, scheduler), `integrations/` (client installers), `utils/` (logging, metrics, db).
- Tests are in `tests/` (pytest with `slow` and `integration` markers).
- Config via CLI flags or environment; copy `.env.example` to `.env` for local dev. Entry points: `zulipchat-mcp`, `zulipchat-mcp-integrate`, `zulipchat-mcp-setup`, `zulipchat-mcp-hook`.

## Build, Test, and Development Commands
- `uv sync` — install dependencies.
- `uv run zulipchat-mcp --zulip-config-file ~/.zuliprc [--enable-listener]` — run server locally.
- `uvx zulipchat-mcp` — quick run via uvx shim.
- Companion commands require an explicit package source: `uvx --from zulipchat-mcp zulipchat-mcp-integrate --help` (also applies to setup and hook commands).
- `uv run python scripts/release_preflight.py --version 0.7.5 --allow-dirty` — validate versions, documentation package sources, and release metadata. CI also runs this gate.
- `uv run pytest -q` — run tests. Use `-m "not slow and not integration"` to skip long tests; `--cov=src` for coverage. Gate is set to 60%.
- `uv run ruff check .` — lint; use Black on changed Python files; `uv run mypy src` — type-check.

## Coding Style & Naming Conventions
- Python 3.10+, 4‑space indent, Black line length 88, Ruff configured (pycodestyle, pyflakes, isort, bugbear, pyupgrade). Keep imports sorted.
- Names: functions/variables `snake_case`, classes `CamelCase`, constants `UPPER_SNAKE_CASE`, modules `lower_snake_case.py`.
- Tool groups should expose `register_*_tools(mcp)` mirroring patterns in `src/zulipchat_mcp/tools/`.

## Testing Guidelines
- Place tests under `tests/` as `test_*.py`; classes `Test*`, functions `test_*`.
- Mark long/external tests with `@pytest.mark.slow` or `@pytest.mark.integration` and gate in CI via markers.
- Prefer fast, deterministic unit tests; mock Zulip API calls. Aim for meaningful coverage with `pytest --cov=src`.
- Testing strategy: always use `uv` (no direct Python invocations), keep tests isolated and network-free by mocking clients, aggressively clean caches/venv before major coverage pushes (`rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache && uv sync --reinstall`), and maintain the coverage gate at 60% while adding minimal, targeted tests without altering functionality.

- Note on contract-only runs: Running only the tests matching `-k "contract_"` will likely trip the global coverage gate; use the full suite for verification, or append `--no-cov` when exploring locally (e.g., `uv run pytest -q -k "contract_" --no-cov`).

## Server-Side LLM Analytics & Protocol (v0.7.3+)

### LLM Analytics Provider Requirements
MCP 2026-07-28 deprecates sampling and recommends direct provider integration. AI analytics tools (`analyze_stream_with_llm`, `analyze_team_activity_with_llm`, `intelligent_report_generator`) call a server-side Anthropic provider (`src/zulipchat_mcp/core/llm.py`) directly:

- `ANTHROPIC_API_KEY`: Required on the server process for LLM generation.
- `ANTHROPIC_MODEL`: Optional model override (defaults to `claude-opus-5`).
- **Graceful degradation**: Without an API key, tools return `status="success"` with `llm_unavailable=True`, `analysis=None`, and raw `data_summary` so calling agents can analyze data directly.
- **No `ctx` parameter**: Analytics tools do not take a `Context` parameter.

### Stateless HTTP Transport
- `--transport http` serves on streamable-HTTP (port 8000 by default).
- Authentication: Set `--auth-token` or `ZULIPCHAT_HTTP_AUTH_TOKEN` (Bearer token auth). Required when binding beyond `127.0.0.1`.
- **Deployment note**: Agent sessions, listener cursors, and default task storage are local. Use a single instance for these workflows; separate DuckDB paths do not make independent replicas interchangeable. HTTP rejects local file paths, event callbacks, and runtime identity switching. Configure `--allowed-host` for public hostnames; Host/Origin validation is always enabled.

### Bidirectional Agent Communication (v0.4+)
Full agent-to-user messaging pipeline available in `src/zulipchat_mcp/tools/agents.py`:
- `register_agent()` - Register a stable agent profile
- `ensure_agent_session()` - Bind a Zulip topic to a live agent session
- `agent_message()` - Send session-scoped messages or lifecycle updates
- `request_user_input()` - Persist in-topic questions or approvals
- `wait_for_response()` - Synchronous polling for persisted responses
- `poll_agent_events()` - Read owner steering/command events from the session topic
- `zulipchat-mcp-hook` - Bridge Claude Code hook events into the same session model

Owner approval replies must include `/approve REQUEST_ID` or `/deny REQUEST_ID`.
Terminal decisions are immutable. A `wait_for_response` timeout leaves the request
pending for another poll; hook permission deadlines still deny on timeout.
Ordinary questions use `/reply REQUEST_ID answer`. Prefer 30-second waits and
retain the same request ID. For reliable steering delivery, poll with
`auto_ack=False`, then acknowledge handled IDs within the same session/agent
scope. Default polling excludes outbound and unauthorized audit records.

For conversational bot entry, an authorized person mentions the Generic bot
normally. `poll_agent_events(mentions_stream="Agents-Channel",
after_message_id=..., auto_ack=False, wait_seconds=20)` reads an event-fed local
inbox without an existing session. The host validates numeric bot, sender and
channel IDs, commits its cursor with a durable work queue, wakes the coding
agent and replies in the source topic. Ordinary mention-driven work does not
require `/reply`; explicit question/approval correlation remains available.
MCP never launches a coding process or treats mention text as executable code.

### Zulip API efficiency (v0.7.4)
- SDK queries share a per-process budget by normalized realm/principal, with
  0.5-second minimum spacing, bounded admission, server-header adaptation and
  `RATE_LIMIT_HIT`/`Retry-After` cooldown. Never transparently retry a write.
- Message windows/details use private identity-scoped snapshots for 15 seconds.
  Identical concurrent requests share a fetch. `fresh=True` on search/detail
  tools bypasses the snapshot. Return source hashes, age, UTC dates, fetched and
  returned counts, and excerpt truncation; a sample is never a complete archive.
- Bot mentions use one lazy long-poll queue per watched channel (maximum four),
  a bounded initial snapshot, message-ID recovery after queue expiration, and
  atomic persistence before event acknowledgement. Host polls read local state.
- Check partial results and listener health. A cursor-retention gap, edited
  input or unverified sender must not silently become an executable host task.
- See [API coverage and efficiency](docs/developer-guide/zulip-api-proxy.md).

### Skills, integrations, and persistent state (v0.7.4)
- Four canonical Agent Skills live in `src/zulipchat_mcp/skills/`; load content
  through dependency-light `skill_content.py`. The FastMCP adapter adds immutable
  Resources and SEP-2640 on MCP 2026-07-28. Resource manifests use exact UTF-8
  byte hashes; preserve full frontmatter and cache metadata.
- Exporters support Claude Code, Codex, OpenCode, Copilot, Antigravity CLI,
  Clio Coder, and generic clients. Native host configuration and portable plugin
  content have separate activation/trust requirements; see
  [Agent Skills](docs/integrations/agent-skills.md).
- Resolve realms and principals through `ConfigManager.resolved_account()`.
  Startup must fail on all account/database initialization errors. Default
  databases are account-scoped; legacy adoption requires an explicit verified
  `ZULIPCHAT_DB_PATH` plus `--associate-existing-db`. Never silently associate
  existing unbound state or reuse another account's database.
- Interactive prompts require listener readiness. Recovery registers a queue
  before backfill, persists per-session message IDs, and deduplicates overlap.
  Persisted decisions/events remain readable when Zulip is unavailable.

### Emoji Registry (v0.4+)
New `src/zulipchat_mcp/core/emoji_registry.py` enforces approved emoji for agent reactions:
- 12 approved emoji: `thumbs_up`, `heart`, `rocket`, `fire`, `tada`, `check_mark`, `warning`, `thinking`, `bulb`, `wrench`, `star`, `zap`
- All others rejected at runtime with helpful error messages
- Use `validate_emoji_for_agent()` to validate before sending reactions


## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `release:` (see `git log`).
- PRs should include: clear summary/motivation, linked issues, tests (or rationale), and example CLI invocation/output when relevant.
- Keep changes minimal and focused; update `README.md`/`AGENTS.md` when behavior or commands change.
- Community PRs are labeled `community`. Prefer merging over reimplementing.

## Distribution & Installation Testing
- **Installation Methods**: Three primary distribution channels:
  - `uvx zulipchat-mcp` (PyPI - fastest, pre-built wheels)
  - `uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp` (GitHub - builds from source)
  - `uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zulipchat-mcp` (TestPyPI - for pre-release testing)
- **Credential Loading**: Supports both zuliprc files and env vars. For config-file paths, environment variables (`ZULIP_CONFIG_FILE`, `ZULIP_BOT_CONFIG_FILE`) are checked before CLI flags. A selected file supplies its email, key, and site together, overriding ambient credential variables. Clients/caches are isolated by configuration and identity; restart after credential-file changes.
- **Claude Code Integration**: Use `--` separator for proper argument passing:
  ```bash
  # Correct syntax (tested)
  claude mcp add zulipchat -e ZULIP_EMAIL=bot@org.com -e ZULIP_API_KEY=key -e ZULIP_SITE=https://org.zulipchat.com -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp
  ```
- **Testing Before Release**: Always run the fake-credential MCP stdio smoke from both the project environment and the built wheel. Use real Zulip credentials only for targeted manual checks of behavior that actually requires Zulip API access.

## Security & Configuration Tips
- Do not commit secrets. Use `.env` (gitignored). Common vars: `ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`.
- Prefer CLI flags for credentials in MCP clients. Message listener startup is lazy by default; `--enable-listener` starts it eagerly for backward compatibility.
- Optional checks before release: `uv run bandit -q -r src` and `uv run pip-audit`.

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
- [Release Checklist](RELEASING.md) - Step-by-step release process
- [Full Documentation Index](docs/README.md)
- [Changelog](CHANGELOG.md)

## Release Process

Full checklist: [RELEASING.md](RELEASING.md)

```bash
uv run python scripts/bump_version.py X.Y.Z   # Bump scripted version locations
# Update CHANGELOG.md manually
uv sync
uv run pytest -q && uv run mypy src && uv run ruff check .
changed_py=$(git diff --name-only -- '*.py')
[ -z "$changed_py" ] || uv run black --check $changed_py
uv build
scripts/pre_release_smoke.sh --version X.Y.Z --allow-dirty
uv run python scripts/release_preflight.py --version X.Y.Z --allow-dirty
git add AGENTS.md CHANGELOG.md CLAUDE.md ROADMAP.md pyproject.toml server.json uv.lock src/zulipchat_mcp tests scripts .github docs README.md CONTRIBUTING.md RELEASING.md
git commit -m "chore: bump version to X.Y.Z"
uv run python scripts/release_preflight.py --version X.Y.Z
git tag vX.Y.Z && git push && git push --tags
gh release create vX.Y.Z --title "vX.Y.Z - Title" --generate-notes --latest
```

Publishing a GitHub release auto-triggers `.github/workflows/publish.yml` which builds and uploads to PyPI via trusted publisher (OIDC). Never leave releases as drafts.

After publishing: comment on fixed issues with version number, credit reporters, invite them to try the update.

## Open Source Community Practices

- **Respond to issues and PRs within 48 hours.** Even "Looking into this" is enough.
- **Label on triage**: `bug`, `enhancement`, `good first issue`, `help wanted`, `community`, `needs-triage`, `dependencies`, `fastmcp`, `mcp-tools`, `breaking-change`.
- **Prefer merging community PRs** over reimplementing the same fix. If already fixed independently, close with explicit credit.
- **After each release**, notify reporters on fixed issues with version and upgrade instructions.
