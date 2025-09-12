# Prompt for Next Cleanup Session (v2.5)

## Executive Summary

  - The v2.5 tool surface is in place and well covered by tests (≥90% gate, fast, offline).
  - Entry points and configuration are clear, CLI‑driven, and align with docs.
  - There are a small number of legacy/duplicate modules and mismatched imports that should be cleaned to avoid drift or runtime surprises in
  less‑tested flows.
  - Documentation exists for v2.5 and a new testing guide; both align broadly with the implemented architecture, but a few stragglers remain from
  earlier versions.

  The core goals for final polish:

  - Eliminate dead/broken re‑exports and legacy imports that point to removed modules.
  - Consolidate or clearly scope duplicated utilities (metrics, scheduler).
  - Ensure public docs match the actual, registered tool surface (v2.5 registrars).
  - Keep all changes surgical; do not regress the fast, deterministic test suite.

---

## Repository Map (current)

  - Entry points and config
      - pyproject.toml → [project.scripts]
          - zulipchat-mcp → zulipchat_mcp.server:main
          - zulipchat-mcp-integrate → zulipchat_mcp.integrations.registry:main
      - src/zulipchat_mcp/server.py
          - CLI flags for Zulip credentials
          - Initializes logging, DB, MCP server, registers v2.5 tool groups
          - Also registers specialized “agent” and “command chain” tools
          - Optional AFK-driven listener thread
      - src/zulipchat_mcp/config.py (CLI + .env)
          - ConfigManager and ZulipConfig dataclass
  - v2.5 tool groups (registered in src/zulipchat_mcp/tools/__init__.py)
      - messaging_v25.py, streams_v25.py, events_v25.py, users_v25.py, search_v25.py, files_v25.py, admin_v25.py
      - Tests: broad and deep coverage for search/streams (focus modules), plus other categories
  - Specialized tools (kept outside v2.5 consolidation, still used)
      - src/zulipchat_mcp/tools/agents.py — AFK mode, agent messaging/status, input requests, task tracking
      - src/zulipchat_mcp/tools/commands.py — command chains abstraction over core command engine
  - Core layer
      - src/zulipchat_mcp/core/client.py — Zulip REST wrapper (caching hooks, identity switching)
      - src/zulipchat_mcp/core/validation/*, core/error_handling.py, core/identity.py, core/commands/*, core/cache.py, core/migration.py
      - src/zulipchat_mcp/core/__init__.py — re‑exports foundation components
  - Services and utilities
      - Services: services/message_listener.py, services/scheduler.py (note discrepancies below)
      - Utilities: utils/database.py (DuckDB), utils/database_manager.py (typed façade), utils/logging.py, utils/metrics.py, utils/topics.py, utils/
  narrow_helpers.py, utils/health.py
  - Documentation
      - v2.5 docs: docs/v2.5.0/* (API refs, guides, troubleshooting)
      - Testing guide: docs/testing/README.md
      - Dev guidelines: AGENTS.md
      - CHANGELOG: 2.5.1 section documenting testing/docs work
  - Tests
      - Fast offline unit/component tests with fakes under tests/tools/*, tests/core/*, tests/utils/*
      - New “contract” tests for output shapes (JSON Schema) for search/analytics/daily summary
      - Coverage gate at 90%; full run ~5–6s

---

## Entry Points and Configuration

  - MCP Server entry
      - zulipchat-mcp → server.py:main()
          - Parses CLI, builds ConfigManager from flags + .env
          - Initializes DuckDB via utils/database.init_database()
          - Builds FastMCP and registers v2.5 tool registrars from tools/__init__.py
          - Registers specialized agents and commands tools
          - Starts an AFK watcher thread that toggles MessageListener (BOT identity)
  - Integration installer
      - zulipchat-mcp-integrate → integrations/registry.py:main()
          - Simple dispatcher to agent installers (Claude Code, Gemini CLI, Opencode)
          - Console tool; out of band from MCP runtime
  - Config shape
      - ConfigManager builds ZulipConfig by preferring CLI args, then ZULIP_* envs
      - has_bot_credentials() and get_zulip_client_config(use_bot=...) support dual identity

  Observations

  - Entry point wiring matches README and docs.
  - Optional listener mechanism: properly controlled by AFK state and `--enable-listener`.

---

## Tool Surface (v2.5) vs. Registered Tools

  - Registered v2.5 tools in server.py:
      - Messaging, Streams, Events, Users, Search, Files, Admin.
  - Additional registered: tools.agents and tools.commands.

  Alignment

  - The v2.5 tool surface is authoritative for MCP; specialized tools are supplementary, not replacements.
  - Tests target v2.5 modules comprehensively (especially search/streams).

---

## Services & Utilities

  - Database
      - utils/database.py: low-level DuckDB connection + migrations + global singleton
      - utils/database_manager.py: typed façade with higher‑level methods used by tools/services
      - Both are used and coherent (façade wraps singleton). Good layering.
  - Logging & Metrics
      - Logging is centralized via utils/logging.py; server.py sets structured logging.
      - There are two metric systems:
          - utils/metrics.py: timers/counters used throughout tools (v2.5 code paths)
          - metrics.py (top‑level): a simplified collector used by dedicated tests
      - This duplication is not harmful but creates potential confusion.
  - Services
      - services/message_listener.py (referenced and used by server AFK watcher)
      - services/scheduler.py (present but not wired correctly — see discrepancies below)
      - src/zulipchat_mcp/scheduler.py re‑exports from services/scheduler but names do not exist in the target module.

---

## Test Suite and Coverage

  - Strategy
      - Fast (≤6s), offline, purely transformation‑layer tests with fakes.
      - Coverage gate 90% enforced; search_v25 and streams_v25 included.
      - Contract tests for output shapes add confidence without brittleness.
  - Not covered (by design)
      - Live Zulip API behavior, auth, DB IO latency, network faults.
      - These can be layered with opt‑in integration tests (already skipped by default).
  - Important reminder
      - Running only `-k "contract_"` under coverage will fail the gate — use full suite or `--no-cov` locally.

---

## Documentation Status

  - docs/v2.5.0/*: API references, user guide, migration guide; broadly consistent with code.
  - docs/testing/README.md: how to run tests, what they cover, fixtures/fakes, coverage gate.
  - AGENTS.md: developer rules, including test strategy and new note about contract‑only runs.
  - CHANGELOG.md: Latest 2.5.0 entry summarizing testing+docs improvements.

---

## Discrepancies, Legacy, and Duplicates (Surgical Cleanup Targets)

  These items should be addressed to prevent runtime surprises and reduce confusion, while keeping changes minimal.

  1. tools.commands legacy import

  - File: src/zulipchat_mcp/tools/commands.py
  - Issue: SearchMessagesCommand.execute() imports ..tools.search.search_messages, but tools/search.py no longer exists (v2.5 uses search_v25.py).
  - Impact: Not exercised by tests (patched in test suite), but would fail if executed in real “command chain” workflows.
  - Low‑risk fix: Replace with the v2.5 surface (e.g., call into search_v25.advanced_search with a tiny adaptor), or delete/disable
  SearchMessagesCommand if not used.

  2. services.scheduler incorrect imports and dangling re‑exports

  - File: src/zulipchat_mcp/services/scheduler.py
      - Uses from .client import ZulipClientWrapper and from .config import ConfigManager (relative to services), which are wrong (should
  be ..core.client or ..config). This module is currently unused by server.py.
  - File: src/zulipchat_mcp/scheduler.py
      - Re‑exports names (cancel_scheduled_message, schedule_message, schedule_reminder) that do not exist in services/scheduler.py (only methods
  exist on MessageScheduler).
  - Impact: Dead/incorrect exports create future runtime hazards if referenced.
  - Options:
      - Remove/disable src/zulipchat_mcp/scheduler.py re‑export module or correct it to export actual callables (thin wrappers over
  MessageScheduler).
      - Either fix services/scheduler.py imports, or explicitly defer adding a public scheduler surface until required; remove from public namespace
  to avoid accidental use.

  3) Dual metrics systems (top‑level vs utils)

  - Files: src/zulipchat_mcp/metrics.py and src/zulipchat_mcp/utils/metrics.py
  - Observation: Both exist and are independently used (top‑level used by tests/test_metrics.py; v2.5 tools use utils.metrics).
  - Impact: Conceptual duplication causes confusion; diverging behavior could mislead diagnostics.
  - Suggestion: Consolidate on utils.metrics (used by tools), and remove zulipchat_mcp/metrics.py. Update tests accordingly.

  4) Legacy or dev scaffolding directories

  - .claude/ appears to be development tooling and statusline scripts; not part of runtime. ensure it's removed from git and not tracked and also removed from origin when push is ready
  - .archived/ holds historical docs moved out of docs/ (good).
  - Impact: None at runtime; noise for newcomers.


  5) Top‑level health wrapper

  - Consolidate the src/zulipchat_mcp/health.py and the utils.health. Once v2.5.0 conventions and code are done, remove legacy health.py


  6) Unused imports in core/agent_tracker and style issues (non‑functional)

  - Previously flagged by Ruff; not critical to function.
  - Suggestion: Sweep for unused imports; fix don't hide the issues

  7) Duplicate “scheduler” concept: services/scheduler and AFK watcher

  - AFK watcher is a minimal thread in server.py; services/scheduler.py implements an HTTPX scheduled message helper that isn’t currently wired.
  - Suggestion: Scheduled messages are included in v2.5 public surface. Thus, fix exports and consolidate to one v2.5.0 scheduled messaging architecture and implementation. If legacy code like AFK is interfering, prefer removing old unused unwired functionality after you incorporate the main concept with the actual new design and implementation. remove relics of all threads and complex old designs and deliver a clean scheduling messaging features and the ability to have a simple toggle for the user is AFK to have the client agent use his bot identity and a specified topic inside the Agents-Channel to start sending messages to the user that way since user is AFK. once returned, the flag is toggled and the agent should stop sending messages automatically to zulip channel and topic but return to normal agent-human behavior instead of agent-zulip message to human- human messages back via zulip-agent cycles when AFK is on.

  8) Documentation backup stray

  - docs/v2.5.0/api-reference/streams.md.backup looks like a dangling backup. Remove to avoid doc duplication.

  9) Commands toolchain surface

  - The command chain (“workflows”) remains but is not part of the seven v2.5 categories. Eliminate

---

## Alignment: Code ↔ Tests ↔ Docs

  - Code
      - v2.5 tools are the primary interface. Specialized tools exist (agents/commands) need to be eliminated after consolidation.
  - Tests
      - Strong coverage on v2.5 search/streams; many other categories well exercised.
  - Docs
      - v2.5 docs and testing docs align. A few minor stragglers remain (backup file, scheduler ambiguity).

  Conclusion: The codebase is functionally aligned with tests and docs for the v2.5 surface. Remaining discrepancies are small and localized.

---

## Verification Checklist (Post‑Cleanup)

  - Build/lint/tests
      - uv sync --reinstall
      - uv run pytest -q (≥90% coverage, ~5–6s)
      - If you unify metrics, update tests/test_metrics.py accordingly.
  - Imports
      - `python -c "import zulipchat_mcp; import zulipchat_mcp.server; import zulipchat_mcp.tools; import zulipchat_mcp.tools.commands"` (no ImportError).
  - CLI smoke
      - `uv run zulipchat-mcp --zulip-email ... --zulip-api-key ... --zulip-site ... --help`
  - Docs verify
      - Confirm no orphan backups under `docs/v2.5.0/*`.
      - Ensure `docs/testing/README.md` still matches the test suite.

---

## Final Notes

  - The test suite is your safety net; keep using the shared fakes and contract tests to validate transformations without hitting the network.
  - Preserve the current fast runtime and coverage gate at 90%.

---

## Actionable To‑Do List (for the next session)

1) tools.commands legacy import
- Replace the legacy import of `..tools.search.search_messages` with a v2.5 adaptor (call `advanced_search` and map), or remove the command if unused.
- Add a minimal smoke test that executes the real command (no patching) with a fake client.

2) Scheduler re‑export mismatch
- Stop exporting non‑existent names from `src/zulipchat_mcp/scheduler.py`, or implement thin wrappers that call `MessageScheduler`.
- Fix incorrect relative imports in `services/scheduler.py` if you decide to keep it active; otherwise de‑scope from the public surface.

3) Metrics consolidation
- Consolidate on `utils.metrics`. Either make `zulipchat_mcp/metrics.py` a façade forwarding to `utils.metrics`, or remove it and update `tests/test_metrics.py`.

4) Docs hygiene
- Move/remove `docs/v2.5.0/api-reference/streams.md.backup`.

5) Optional dev scaffolding
- Move `.claude/` to `.archived/claude/` or add a README clarifying it as dev tooling.

Acceptance criteria
- Full suite passes with ≥90% coverage.
- No import/run‑time errors in CLI help or module imports.
- README/docs/testing remain accurate.
  - The issues identified are small, targeted, and won’t change the server’s public promise — they just reduce drift and eliminate edge‑case runtime
  errors.
