# Changelog

All notable changes to ZulipChat MCP are documented in this file.

## [Unreleased]

## [0.7.3] - 2026-09-16

### Security
- Agent replies now verify the session owner and matching topic/session before answering a request. Supplying a request ID from another topic or another sender can no longer bypass approval checks. Unbound legacy requests are no longer answered from inbound messages.
- Replaced command-condition Python `eval` with a bounded data-expression interpreter supporting comparisons, boolean logic, indexing, `dict.get`, and `len`. Arbitrary calls and attribute traversal are rejected.
- Public HTTP binds now fail startup without a non-empty bearer token. Host and Origin validation is explicitly enabled; `--allowed-host` and `--allowed-origin` configure trusted deployments.
- Authenticated downloads are restricted to attachment paths on the configured Zulip origin, reject path traversal, and do not follow redirects. Upload reads and streamed downloads enforce the 25 MB size limit.
- HTTP tools reject local filesystem paths, outbound event callbacks, and process-wide identity switching. Local stdio retains these capabilities. Attachment deletion now requires `--unsafe`.
- Updated affected runtime and development dependencies after an advisory audit, with security floors for the HTTP/authentication stack.

### Fixed
- Preserve DuckDB write-ahead logs during lock retries so crash recovery can replay committed data.
- Remove eager network cache warmup from startup; startup and `server_info` no longer depend on Zulip API availability. Invalid configuration exits with a nonzero status.
- Advance event cursors before filtering to avoid replaying excluded events, validate listener bounds, and run long polls outside the MCP event loop.
- Add a timeout to the upload fallback and treat blank analytics model settings as unset.

### MCP migration
- Move from the FastMCP 4 beta to FastMCP 4.0.4 and MCP SDK/types 2.2.0, retaining 20 core and 60 extended tools and opt-in SEP-2663 tasks (addresses #17).
- Remove the protocol monkey patch. Upstream closed python-sdk#3273 as intentional: ping is absent from the modern protocol surface. Smoke tests retain legacy ping and exercise modern discovery/tool calls (supersedes the original removal criterion in #18).
- Test both protocol eras and both tool tiers from source and built wheels with isolated fake credentials and temporary databases.
- Correct documentation: MCP sampling is deprecated, rather than removed, in 2026-07-28. Server-side Anthropic analytics remain the chosen migration path.
- Document single-instance agent/session deployment requirements and HTTP migration constraints.

This release also includes the previously unpublished `0.7.3-beta.1` fixes below. Community contributions from @aurelien-eveil (drafts) and @lloydhazlett (listener long polling) are retained.

## [0.7.3-beta.1] (2026-08-09)

### Fixed
- AI analytics now distinguish an unconfigured provider from a configured provider that returns no usable text. Empty responses surface as errors, while responses stopped at `max_tokens` report truncation explicitly.
- Anthropic responses retain every text block while continuing to exclude thinking and tool blocks.
- Draft creation and editing now accept stream names and user names in addition to raw IDs. Stream names resolve through the Zulip client, and private recipients use the existing cached fuzzy user resolution. The draft tools were originally contributed in PR #15 by @aurelien-eveil.
- The temporary 2026-07-28 ping compatibility patch now runs at package import so embedded ASGI and framework runner entry points cannot bypass it.

### Changed
- AI analytics use low provider effort to reduce latency and cost while retaining the 8192 token response budget. The Anthropic dependency floor is now 0.78.0, the first SDK release that supports `output_config.effort`.
- The Anthropic client is reused across analytics calls in the server process.

### Maintenance
- Added issue #17 to track the FastMCP 4.0.0 final migration checks.
- Added issue #18 to track removal of the temporary mcp-types ping compatibility patch.

## [0.7.3-beta] - 2026-08-08

### Added
- **MCP 2026-07-28 Stateless Protocol Support**: Upgraded to FastMCP 4 (`fastmcp[tasks]==4.0.0b2`), migrating the server to the 2026-07-28 stateless protocol. Includes dual-era protocol compatibility (serving both 2025-11-25 and 2026-07-28 clients).
- **Stateless HTTP Transport (`--transport http`)**: Added `--transport http`, `--host`, `--port`, and `--auth-token` CLI flags (supported via `ZULIPCHAT_HTTP_AUTH_TOKEN` environment variable). Exposes streamable-HTTP with bearer token authentication for centralized or remote MCP deployments.
- **Remote Integration Snippets**: Extended `zulipchat-mcp-integrate print` with `--remote-url` and `--remote-token` options for `claude-code`, `vscode`, and `generic` clients. Updated `server.json` manifest with a `streamable-http` remote template.
- **SEP-2663 Tasks Extension**: Registered `TasksExtension` (`fastmcp-tasks`) on the FastMCP server, preserving background task execution (`teleport_chat`, `wait_for_response`, `listen_events`) under FastMCP 4.
- **Protocol Compatibility Patch (`core/compat.py`)**: Added a temporary compatibility patch for upstream [python-sdk#3273](https://github.com/modelcontextprotocol/python-sdk/issues/3273) to restore ping keepalives on 2026-07-28 connections.

### Breaking Changes & Migration
- **Server-Side LLM Analytics (`core/llm.py`)**: Removed MCP client-side sampling (`ctx.sample`, removed in FastMCP 4). AI-powered analytics tools (`analyze_stream_with_llm`, `analyze_team_activity_with_llm`, `intelligent_report_generator`) now execute via a server-side Anthropic LLM provider directly using `ANTHROPIC_API_KEY`.
- **Migration Note**: If you use AI analytics tools, set `ANTHROPIC_API_KEY` on the `zulipchat-mcp` server process. Without an API key, analytics tools degrade gracefully returning `status="success"` with `llm_unavailable=True` and structured `data_summary` so calling agents can process the data directly.
- **Parameter Changes**: Removed injected `ctx: Context` parameter from analytics tool signatures.

### Fixed
- Default analytics model is `claude-opus-5`. The previously configured `claude-3-5-sonnet-latest` names a retired model and returns a 404 on every analytics call. Override with `ANTHROPIC_MODEL`.
- Declared `anthropic` as a direct dependency instead of relying on the `fastmcp[anthropic]` extra, which existed to supply the now-removed sampling handler. Without it, a future FastMCP release dropping that extra would silently degrade every analytics tool to `llm_unavailable=True`.
- Raised the analytics generation budget to 8192 tokens. Current models think by default and `max_tokens` bounds thinking plus response text together, so the previous 2048 truncated summaries mid-sentence.
- `zulipchat-mcp-integrate print --remote-url` now reports an argparse error for clients without a remote snippet instead of raising an uncaught `ValueError`.

## [0.7.2] - 2026-08-04

### Added
- **Native Zulip Drafts Tools**: Added extended tools for listing (`get_drafts`), creating (`create_draft`), editing (`edit_draft`), and deleting (`delete_draft`) drafts through Zulip's native drafts API (`/drafts`), bringing the extended tool count to 60. (PR #15, credit: @aurelien-eveil)

### Fixed
- **Listener Long-polling Read Timeout**: Enabled `longpolling=True` on Zulip `/events` listener requests to set the HTTP timeout to 90s, matching the server's 30s long-poll hold timeout and preventing spurious 15s `Read timed out` crashes and exponential backoff loops during idle periods. (PR #14, credit: @lloydhazlett)

### Chore
- **Repo-wide Line Ending Normalization**: Added `.gitattributes` (`* text=auto eol=lf`) and normalized line endings from CRLF to LF across 25 repository files to prevent noisy line-ending diffs across platforms. (PR #13, credit: @lloydhazlett)

## [0.7.1] - 2026-05-11

### Fixed
- Restored v0.7.x startup under FastMCP 3 by installing the task extra (`fastmcp[anthropic,tasks]`) and disabling accidental server-wide task advertisement. Reported by @jessealama in #10 and addressed by @jessealama's PR #11, with additional confirmation from @peteWT and @jpuritz in #12.
- Made MCP task support explicit and opt-in for long-running tools only: `teleport_chat`, `wait_for_response`, and `listen_events` now advertise optional background-task support while normal fast tools remain standard calls.
- Converted `teleport_chat(wait_for_reply=True)` and `wait_for_response` to async-safe implementations so task-enabled calls do not block the server event loop.
- Moved background service startup and shutdown into the FastMCP lifespan, giving the Zulip listener a managed teardown path instead of process-lifetime threads.

### Tests
- Added real FastMCP registration coverage for core and extended tools, including a regression guard that prevents reintroducing server-wide `tasks=True`.

### Docs
- Modernized `CLAUDE.md`: removed stale v0.4 import patterns, fixed the local connection-test snippet to use installed-package imports, documented the `register_tool` / `optional_background_task` pattern from `tools/registration.py`, the 20-core / 56-extended tool modes (`--extended-tools` / `ZULIPCHAT_EXTENDED_TOOLS=1`), and the three project skills under `.claude/skills/`.
- Switched GitHub releases to `gh release create --generate-notes`. `RELEASE.md` removed; `CHANGELOG.md` is the single source of release notes.
- `ROADMAP.md` v0.7.1 date corrected to 2026-05-11 to match `CHANGELOG.md`.

## [0.7.0] - 2026-05-01

### Added
- **Agent control plane** for session-scoped Claude Code workflows. New core tool `ensure_agent_session` and extended tools `list_sessions`, `close_agent_session`, backed by a stable agent profile registered via the rebuilt `register_agent`.
- **Claude Code plugin** at `integrations/claude-code/plugin/` with `.claude-plugin/plugin.json`, hook bridge, three skills (`zulipchat-session-operator`, `zulipchat-notifyme`, `zulipchat-loop`), and the `zulip-session-operator` subagent.
- **Standalone `.claude/` template** at `integrations/claude-code/.claude/` for users who want to vendor the integration into their own repo without the plugin format.
- **`zulipchat-mcp-hook` CLI** that bridges Claude Code lifecycle events (`SessionStart`, `PermissionRequest`, `PostToolUseFailure`, `Notification idle_prompt`, `StopFailure`, `TaskCompleted`, `SessionEnd`) into the bound Zulip topic.
- **`zulipchat-mcp-integrate export --client claude-code`** subcommand to generate the plugin or standalone scaffold into a target directory, with bot-config and extended-tools modes.
- DuckDB tables `agent_profiles`, `agent_sessions`, `agent_requests`, `session_events`. Migration is additive; existing tables and rows are untouched.

### Changed
- `register_agent` now accepts optional `agent_name`, `owner_email`, `stream_name`, `topic_prefix`, `metadata` keyword arguments. Existing calls without arguments still work. The return shape is new: `agent_id`, `agent_name`, `agent_type`, `owner_email`, `stream`, `topic_prefix`.
- `agent_message`, `request_user_input`, and `wait_for_response` now operate session-scoped against the topic bound by `ensure_agent_session`. The previous channel-broadcast behavior is replaced.
- Hook commands in the Claude Code plugin invoke `uvx --from zulipchat-mcp zulipchat-mcp-hook` so the bridge resolves whether the package is installed persistently or run ephemerally.
- Setup wizard command corrected to `uvx --from zulipchat-mcp zulipchat-mcp-setup` across README, troubleshooting, installation, quick-start, and setup-wizard docs. (PR #9, credit: @odurif0)

### Removed
- AFK mode tools `enable_afk_mode`, `disable_afk_mode`, `get_afk_status`, and the merged `afk_mode` tool. The session model (`ensure_agent_session` plus `close_agent_session`) replaces them.

### Upgrading from 0.6.x
- DuckDB schema upgrade runs automatically on first start of v0.7.0. No manual migration is required.
- Scripts that called the AFK tools must be updated to the session model.
- Scripts that parsed the previous `register_agent` return keys must read from the new keys (`agent_id`, `stream`, `topic_prefix`).
- For the new Claude Code plugin, install via Claude Code's plugin command and ensure `~/.zuliprc` (and optionally `~/.zuliprc-bot`) exist. Hooks call `uvx --from zulipchat-mcp zulipchat-mcp-hook`, so no global package install is required.

## [0.6.2] - 2026-03-03

### Fixed
- **Critical: Rate limit exhaustion** — Message listener was hardcoded to start on every server boot, long-polling Zulip's `/events` endpoint regardless of the `--enable-listener` flag. Multiple MCP client sessions would all poll simultaneously, exhausting the per-user rate limit. Listener is now off by default and lazy-started only when an agent tool that needs it is invoked. (PR #8, credit: @klutchell)
- **Tight-loop on API errors** — When the listener received a 429 or other error response, it returned an empty list and immediately retried with no delay, generating thousands of requests per minute. Now returns a sentinel on error and applies exponential backoff (2s base, 120s cap).
- **Stale DuckDB lock after unclean shutdown** — When a server process died without closing the database, the WAL file persisted and blocked all new connections permanently. The database layer now extracts the locking PID from DuckDB's error message, checks if the process is alive, and removes the stale WAL file if the process is dead. (Fixes #7, reported by: @JaimeCernuda)

## [0.6.1] - 2026-02-23

### Added
- `zulipchat-mcp-integrate` CLI for generating copy-paste integration snippets across MCP clients.
- Integration package templates under `integrations/` for Claude Code, Gemini CLI, Codex, OpenCode, VS Code/Copilot, Cursor, Windsurf, Antigravity, and generic MCP clients.
- Automated release preflight checklist: `scripts/release_preflight.py`.
- Automated pre-release smoke runner: `scripts/pre_release_smoke.sh`.
- New setup wizard and integration docs: `docs/user-guide/setup-wizard.md`, `docs/integrations/*`.

### Changed
- Setup wizard (`zulipchat-mcp-setup`) now supports core vs extended tool mode, additional client targets, and config-file output paths.
- Publish workflow hardened with stricter version checks and wheel-installed entrypoint smoke tests before PyPI publish.
- Documentation refreshed and expanded for v0.6.x across user guide, API reference, integration pages, security/support/community docs, and contributor guides.
- Packaging metadata and source distribution contents aligned with public docs/integrations assets.

### Fixed
- `--debug` now correctly enables DEBUG-level structured logging in `zulipchat-mcp`.
- Setup wizard exits cleanly in non-interactive terminals and better prioritizes user vs bot zuliprc selection defaults.
- Release smoke script now installs the exact wheel for the target version, avoiding multi-wheel conflicts in `dist/`.

## [0.6.0] - 2026-02-22

### Changed
- **Two-tier tool registration**: Default mode registers 19 core tools (~87% token reduction); `--extended-tools` flag or `ZULIPCHAT_EXTENDED_TOOLS=1` enables full set (~55 tools)
- **7 merged tools**: `manage_message_flags` (replaces 7 flag tools), `get_user` (replaces by-id + by-email), `manage_user_mute`, `toggle_reaction`, `manage_task`, `afk_mode`, `manage_scheduled_message`
- **CLI**: Added `--extended-tools` argument to `server.py`
- **Concise descriptions**: Core and extended tool descriptions optimized for token efficiency

### Removed
- **events.py stub**: Dead code that delegated to agents.py removed
- **Legacy registration path**: `server.py` no longer calls individual `register_*_tools()` functions; uses `register_core_tools()` / `register_extended_tools()` instead

### Added
- `register_core_tools()` and `register_extended_tools()` in `tools/__init__.py`
- `tests/tools/test_tool_tiers.py`: 36 tests covering registration counts, merged tool dispatch, error paths

---

## [0.5.3] - 2026-02-22

### Fixed
- **CI fully green**: Resolved all CI failures across Python 3.10/3.11/3.12 — 10 mypy errors, 1 test failure, 2 ruff lint errors
- **Null credential guards**: Added validation in `identity.py` and `scheduler.py` to fail fast on missing credentials instead of passing `None`
- **Test compatibility**: Fixed enum `str()` rendering difference between Python 3.10 and 3.11+ in narrow filter tests
- **Type annotations**: Added missing return types in `config.py`, type annotation for `database.py` singleton flag

### Added
- **Auto-publish workflow**: `publish.yml` builds and uploads to PyPI via trusted publisher when a GitHub release is published
- **Issue templates**: Bug report and feature request templates with structured fields
- **PR template**: Checklist matching CONTRIBUTING.md standards
- **Release checklist**: `RELEASING.md` with step-by-step release runbook
- **Repo discoverability**: GitHub Discussions enabled, topics added, homepage set to PyPI

### Changed
- **Agent guides updated**: CLAUDE.md and AGENTS.md now codify release process, open-source community practices, and correct coverage gate (60%, not 85%)
- **Tool counts corrected**: README and RELEASE.md now match actual registered tools (Messaging: 16, System: 5, Total: 67)
- **Labels**: Added project-specific labels (`community`, `fastmcp`, `mcp-tools`, `dependencies`, `breaking-change`, `needs-triage`) and retroactively labeled all issues/PRs
- **bump_version.py**: Fixed stale POLISHING.md reference, now targets RELEASE.md

---

## [0.5.2] - 2026-02-22

### Added
- **Teleport-Chat** (`teleport_chat` tool): Bidirectional agent-human messaging via Zulip DMs and channels. Bot identity for private back-channel; user identity for all org-facing actions. Supports fuzzy name resolution and optional wait-for-reply
- **Fuzzy User Resolution** (`resolve_user` tool): Resolve display names to Zulip emails with fuzzy matching — "Jaime" just works without knowing the formal email
- **Always-On Message Listener**: Listener runs automatically on startup (no longer gated behind `--enable-listener`). Receives all messages (DMs + streams), not just Agents-Channel
- **Queue State Persistence**: Listener queue ID and last_event_id survive restarts via `listener_state` DB table
- **AFK Auto-Return**: `auto_return_at` is now computed from `hours` parameter and enforced — AFK mode expires as expected
- **Cache Warmup**: User and stream caches pre-populated on server startup for instant fuzzy resolution

### Fixed
- **`poll_agent_events` always empty**: `_process_message` returned early when no `request_id` matched, never inserting into `agent_events`. Now always stores events
- **Listener missed DMs**: Event queue was narrowed to Agents-Channel only. Removed narrow — bot now receives all visible messages
- **AFK `auto_return_at` never set**: `set_afk_state` hardcoded `NULL`. Now computes expiry from hours
- **Zulip display vs delivery email mismatch**: Added `is_same_user()` to `UserCache` to correctly match `user12345@org.zulipchat.com` against `name@university.edu`

### Changed
- `--enable-listener` flag kept for backward compat but listener is now always-on
- `ServiceManager` always starts regardless of flag or AFK state

---

## [0.5.1] - 2026-02-22

### Fixed
- **FastMCP 3.0 Upgrade**: Replaced removed `on_duplicate_tools/resources/prompts` and `include_fastmcp_meta` constructor kwargs with `on_duplicate="warn"` (Issue #4)
- **File Download URLs**: Normalized `/user_uploads/` paths to full `https://` URLs and resolved auth by identity (Issue #3)
- **Broken Test Suite**: Fixed 5 test files with missing mock patches, stale DB API references, and syntax errors (520 tests passing)

### Changed
- Pinned `fastmcp[anthropic]>=3.0.0,<4.0.0`

---

## [0.5.0] - 2026-01-22

### Changed
- ConfigManager now uses singleton pattern for consistent CLI arg handling
- All logging outputs to stderr (no stdout pollution for MCP STDIO)

### Added
- SECURITY.md with responsible disclosure policy

### Fixed
- CLI arguments now respected by all tools (singleton config)

---

## [0.4.3] - 2025-01-21

### Fixed
- **Search Timeout**: Fixed `search_messages` timeout when using time filters without narrow (15s → <1s)
- **Daily Summary**: Fixed `get_daily_summary` returning 0 messages due to invalid `sent_after:` operator
- **Wildcard Search**: Fixed wildcard query `*` returning empty results
- **Python 3.12+**: Fixed `datetime.utcnow()` deprecation warnings

### Improved
- **Test Coverage**: Increased from 66% to 69% (484 tests, 0 warnings)

---

## [0.4.2] - 2025-01-20

### Added
- **Privacy Policy**: Added `PRIVACY.md` and privacy section in README (required for MCP directory listings)
- **MCP Registry Metadata**: Added `server.json` for Official MCP Registry submission
- **Registry Verification**: Added `mcp-name` metadata for PyPI package ownership verification

### Documentation
- Prepared for submission to Official MCP Registry, Smithery.ai, Glama.ai, and other directories
- Added comprehensive privacy policy documentation

---

## [0.4.1] - 2025-01-19

### Fixed
- Updated README with correct PyPI install instructions

---

## [0.4.0] - 2025-01-19

### Added
- **Setup Wizard**: Interactive `zulipchat-mcp-setup` command for guided configuration
- **zuliprc-first Authentication**: Credentials now loaded from zuliprc files (more secure than CLI args)
- **Anthropic Sampling Handler**: Fallback handler for LLM analytics when MCP sampling unavailable
- **249 New Tests**: Comprehensive test suite from Gemini QA audit (411 total tests)
- **Emoji Registry**: Approved emoji validation for agent reactions (`src/zulipchat_mcp/core/emoji_registry.py`)

### Changed
- **Version Reset**: Moved from 2.5.x to 0.4.x versioning scheme
- **MCP Spec Compliance**: Improved sampling, emoji registry, and error messages
- **Coverage Threshold**: Adjusted to 60% (realistic for full codebase testing)
- **Smart Stream Fallback**: Agent tools now fallback gracefully when streams unavailable
- **execute_chain Context**: Proper context initialization for workflow chains

### Fixed
- Resolved 5 bugs from Gemini QA audit
- Resolved 3 bugs from MCP stress testing
- Strict typing gaps and SDK mismatches
- Removed orphaned v25 modules and broken imports
- Removed MCP sampling dependency from AI analytics tools (now optional)

### Documentation
- Standardized version references to 0.4.x across all docs
- Fixed coverage gate documentation (60% across all files)
- Updated release documentation structure

---

## [0.3.0] - 2024-12-01

### Major Architecture Consolidation
- **24+ tools → 7 categories**: Complete consolidation with foundation layer
- **Foundation Components**: IdentityManager, ParameterValidator, ErrorHandler, MigrationManager
- **New Capabilities**: Event streaming, scheduled messaging, bulk operations, admin tools
- **Multi-Identity**: User/bot/admin authentication with capability boundaries
- **100% Backward Compatibility**: Migration layer preserves all legacy functionality

### Tool Categories
1. **Core Messaging** (`messaging.py`) - 4 consolidated tools with scheduling, narrow filters, bulk operations
2. **Stream & Topic Management** (`streams.py`) - 3 enhanced tools with topic-level control
3. **Event Streaming** (`events.py`) - 3 stateless tools for real-time capabilities
4. **User & Authentication** (`users.py`) - 3 identity-aware tools with multi-credential support
5. **Advanced Search & Analytics** (`search.py`) - 2 enhanced tools with aggregation capabilities
6. **File & Media Management** (`files.py`) - 2 enhanced tools with streaming support
7. **Administration & Settings** (`admin.py`) - 2 admin tools with permission boundaries

### Technical Improvements
- Sub-100ms response times for basic operations
- Stateless event architecture with ephemeral queues
- Standardized error responses across all tools
- Progressive disclosure interface (basic/advanced modes)

---

## [0.2.0] - 2024-11-01

### Initial Public Release
- Core messaging and search functionality
- Stream management tools
- User management tools
- Basic event handling
- DuckDB persistence layer
- FastMCP framework integration
