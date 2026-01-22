# ZulipChat MCP v0.5.0 Hardening Release

## What This Is

A Model Context Protocol server that enables AI assistants (Claude, Gemini) to interact with Zulip Chat workspaces. Built on FastMCP with DuckDB persistence and dual identity support. This is a hardening release — stability and polish for first public push, no new features.

## Core Value

Production-ready MCP server that "just works" — install with one command, configure with existing zuliprc, integrate with Claude/Gemini seamlessly.

## Requirements

### Validated

<!-- Shipped and confirmed valuable in v0.4.x -->

- ✓ Dual identity system (user/bot credentials) — v0.4.0
- ✓ 65 MCP tools across 8 categories — v0.4.0
- ✓ FastMCP framework with Anthropic sampling — v0.4.0
- ✓ DuckDB persistence for agent state — v0.4.0
- ✓ Background services (message listener, scheduler) — v0.4.0
- ✓ CLI entry points (zulipchat-mcp, setup wizard, integrate) — v0.4.0
- ✓ PyPI distribution working — v0.4.3
- ✓ 69% test coverage — v0.4.3
- ✓ Structured logging via structlog — v0.4.0

### Active

<!-- v0.5.0 scope - hardening only -->

**Critical Fix:**
- [ ] ConfigManager module-level state (CLI args ignored bug)

**README Overhaul:**
- [ ] Focus on 8 tool categories (not 65 tool count)
- [ ] Progressive disclosure in installation section
- [ ] Standard badges (downloads, stars, last commit)

**Documentation Sync:**
- [ ] Version 0.5.0 consistent across all files
- [ ] CLI arg references match actual implementation
- [ ] SECURITY.md created with disclosure policy
- [ ] All documentation links valid

**Release Infrastructure:**
- [ ] Version bump script (single source of truth)
- [ ] CI version check enforcement
- [ ] PyPI Beta classifier (not Production/Stable)
- [ ] PEP 639 license-files compliance
- [ ] GitHub Release for v0.5.0

**Code Quality:**
- [ ] No stdout in STDIO MCP server (verify structlog to stderr)
- [ ] Tool descriptions token-optimized

### Out of Scope

- New features — hardening only release
- OAuth/SSO integration — complexity, not core value
- Mobile app support — web-first
- Real-time WebSocket events — polling works, complexity not justified
- v1.0 release — needs community adoption signal first

## Context

**Brownfield project:** v0.4.3 is published and working. This is polish/hardening for first public marketing push.

**Known bug:** ConfigManager instantiated fresh in each tool, ignoring CLI args. Fix is module-level state pattern (validated against MCP spec).

**Target audience:** AI developers building agents with Claude/Gemini who want Zulip team chat integration.

**Existing codebase:** ~50 Python files, 65 tools, well-structured layers (config → core → tools → services → utils).

## Constraints

- **No new features:** Hardening only — stability over scope
- **Single session:** Plan and execute in one session
- **Beta maturity:** PyPI classifier is Beta, not Production/Stable
- **Backwards compatible:** No breaking changes from v0.4.x

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Module-level config state | MCP spec validates this pattern; tools import singleton | — Pending |
| Categories not counts | "8 categories" clearer than "65 tools" for marketing | — Pending |
| Progressive disclosure | Simple install first, details in collapsibles | — Pending |
| Beta classifier | Honest maturity level; v1.0 when community justifies | — Pending |
| Feature-driven releases | Quality over schedule; release when ready | — Pending |

---
*Last updated: 2026-01-21 after initialization*
