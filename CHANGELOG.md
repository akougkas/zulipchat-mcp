# Changelog

All notable changes to ZulipChat MCP are documented in this file.

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
