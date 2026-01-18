Testing Guide (v0.4)

Overview
- This repository uses fast, offline unit/component tests to validate the transformation layer of the tools (parameter handling, branching, aggregations, and response shaping).
- Integration tests exist but are opt-in and skipped by default.

Quick Start
- Install deps (repo-local cache recommended in sandboxes):
  - `UV_CACHE_DIR=.uv_cache uv sync`
- Run full suite with coverage gate (90%):
  - `UV_CACHE_DIR=.uv_cache uv run pytest -q`
- Fast local filters:
  - Only search/streams tools: `uv run pytest -q -k "search_v25 or streams_v25"`
  - Skip slow/integration: `uv run pytest -q -m "not slow and not integration"`

What These Tests Cover
- Parameter transformation and validation
- Message processing, filtering, and search windowing (newest/oldest/relevance)
- Business logic: aggregations, analytics, daily summaries, derived insights
- Response formatting: counts, has_more, metadata, chart_data, detailed_insights
- Error branching and exception handling
- Time ranges → narrow filter construction

What They Don’t Cover (by design)
- Live Zulip API calls and auth
- Security controls, DB operations, MCP protocol compliance
- Network fault behavior and full end‑to‑end flows

Fixtures & Fakes
- `make_msg`: builds Zulip‑like messages with timestamp offsets and optional fields
- `fake_client_class`: tiny base to define only the client methods a test needs
- Patching `_get_managers` isolates logic from global managers/identities

Contract Tests
- JSON‑schema checks validate top‑level shapes for transformation outputs:
  - `advanced_search` (messages/topics)
  - `analytics` (activity/sentiment/topics/participation)
  - `get_daily_summary`
- Note: Contract tests assert structure, not exact values. They allow `additionalProperties` to avoid brittleness during refactors.

Coverage Gate
- Enforced at 90% via `pyproject.toml` (`--cov-fail-under=90`).
- Running only a small subset can under‑report coverage; prefer full runs.

Tip: contract-only runs
- Running only `-k "contract_"` will trip the coverage gate; use the full suite for verification or append `--no-cov` when exploring locally:
  - `uv run pytest -q -k "contract_" --no-cov`

Cleaning & Reinstall
- Aggressive clean for fresh coverage:
  - `rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache && uv sync --reinstall`

Performance Notes
- Suite runs in ~5–6s locally.
- Keep tests deterministic; avoid `sleep`, network, or real API objects.

