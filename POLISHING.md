# POLISHING.md - v0.5.0 Release Preparation

## Overview

This document outlines the comprehensive polishing effort to prepare ZulipChat MCP for its first public release as v0.5.0. The version bump from 0.4.x to 0.5.0 signifies the maturity and hardening of the MCP server.

**Target Release**: v0.5.0
**Status**: Planning Complete - Ready for Execution
**Created**: 2026-01-22
**Interview Rounds**: 5 (20 questions answered)

---

## Interview Decisions Summary

| Area | Decision | Rationale |
|------|----------|-----------|
| **Config Fix** | Module-level state | Store config at module level during server init. Tools import it. |
| **v0.5.0 Goal** | Both stability + marketing | Comprehensive polish release for first public push |
| **Audience** | AI developers | People building agents with Claude/Gemini who want Zulip integration |
| **Versioning** | Single source + CI | pyproject.toml is truth, auto-update script, CI enforcement |
| **Tool Display** | Categories not counts | "8 tool categories" instead of "65 tools" |
| **Install Docs** | Progressive disclosure | Simple start, collapsible details for depth |
| **Stale Docs** | Targeted fixes | Fix broken parts, keep good content |
| **Release Cadence** | Feature-driven | Quality over schedule, release when ready |
| **SECURITY.md** | Full policy | Professional security disclosure process |
| **Coverage** | Quality focus (>50%) | No artificial targets, focus on test quality |
| **GitHub Releases** | Major only | 0.5, 0.6, 1.0 get releases; patches get tags only |
| **v0.5.0 Scope** | Hardening only | No new features, clean polish release |
| **v1.0 Vision** | Community signal | When adoption/stars/contributors justify it |
| **PyPI Maturity** | Beta | "Development Status :: 4 - Beta" classifier |
| **Badges** | Standard set | PyPI downloads, GitHub stars, last commit |
| **Agent Execution** | Staged waves | 2-3 parallel agents at a time |
| **Blockers** | Fix all | No release until everything is clean |
| **Timeline** | This session | Plan now, execute in next session |
| **Post-v0.5.0** | Community focus | Adoption, tutorials, examples, outreach |

---

## Phase 0: Tool Description Optimization (Start Here)

### 0. Token-Efficient Tool Descriptions (P0 - Investigation)

**Context**: MCP tool descriptions are sent to the LLM with every request. Verbose descriptions consume tokens and increase costs. With 65 tools, this overhead compounds significantly.

**Research Needed**:
- [ ] Audit current tool description lengths across all 65 tools
- [ ] Identify verbose/redundant descriptions
- [ ] Research MCP best practices for concise tool metadata
- [ ] Measure token count of current tool registry
- [ ] Establish target token budget per tool description

**Optimization Goals**:
- Concise, action-oriented descriptions (1-2 sentences max)
- Remove redundant phrases ("This tool...", "Use this to...")
- Consolidate similar tools where possible
- Ensure parameter descriptions are minimal but clear

**Files to Audit**:
- `src/zulipchat_mcp/tools/*.py` - All `@mcp.tool()` decorators and docstrings

**Impact**: Lower token overhead = faster responses, lower costs, better UX

---

## Critical Bug Fixes

### 1. ConfigManager CLI Args Bug (P0 - Blocker)

**Problem**: Each tool function creates a new `ConfigManager()` without passing CLI arguments. This causes `--zulip-config-file` and `--zulip-bot-config-file` to be ignored at runtime.

**Location**: All tool files in `src/zulipchat_mcp/tools/*.py`

**Current (Broken)**:
```python
async def send_message(...):
    config = ConfigManager()  # Ignores CLI args!
    client = ZulipClientWrapper(config)
```

**Root Cause**: Tools create fresh ConfigManager instances instead of using the one initialized at server startup with CLI args.

**Chosen Fix**: Module-level State (per interview decision)

**Validation (from MCP Spec Research):**
- Module-level state is **consistent with official MCP best practices**
- Lifespan pattern is for async resources (DB connections, HTTP clients), not config
- Configuration loaded at startup is correctly handled via module-level state
- The `get_config()` accessor pattern matches official documentation examples

**Implementation**:
```python
# In src/zulipchat_mcp/config.py
_global_config: ConfigManager | None = None

def init_global_config(config_file: str | None = None, bot_config_file: str | None = None, debug: bool = False) -> ConfigManager:
    """Initialize global config at server startup."""
    global _global_config
    _global_config = ConfigManager(config_file, bot_config_file, debug)
    return _global_config

def get_config() -> ConfigManager:
    """Get the global config instance."""
    if _global_config is None:
        # Fallback for testing or direct usage
        return ConfigManager()
    return _global_config
```

**Files to Modify**:
- `src/zulipchat_mcp/config.py` - Add module-level state
- `src/zulipchat_mcp/server.py` - Call `init_global_config()` at startup
- All tool files - Replace `ConfigManager()` with `get_config()`

---

## README Overhaul

### 2. Tool Presentation (P1)

**Decision**: Focus on categories, not raw count

**Current**: "Transform your AI assistant into a Zulip power user with 40+ tools via MCP"

**New**: "Transform your AI assistant into a Zulip power user with 8 powerful tool categories via MCP"

**Categories to highlight**:
1. Messaging (send, edit, search, reactions)
2. Streams & Topics (management, analytics)
3. Real-time Events (webhooks, long-polling)
4. User Management (identities, groups, profiles)
5. Search & Analytics (AI insights, sentiment)
6. Files & Media (upload, share, metadata)
7. Agent Communication (tasks, AFK, workflows)
8. System & Workflow (chains, documentation)

### 3. Installation Section (P1)

**Decision**: Progressive disclosure

**Structure**:
1. Quick Start (1 command)
2. Claude Code (simple)
3. <details> Gemini CLI
4. <details> Claude Desktop / Cursor / VS Code
5. <details> Advanced: Dual Identity

### 4. Tool Category Table Audit (P1)

**Action Items**:
- [x] Verify category structure (8 categories confirmed)
- [ ] Count tools per category programmatically
- [ ] Update capabilities descriptions
- [ ] Use progressive disclosure in table

### 5. Badges Update (P1)

**Decision**: Add standard social proof badges

**Current badges**:
- MCP Compatible
- License MIT
- Python 3.10+
- Version
- Release
- Coverage
- Code Style Black

**Add**:
- PyPI Downloads
- GitHub Stars
- Last Commit

---

## Documentation Sync

### 6. Cross-Document Consistency (P1)

**Files to Audit**:
- `CLAUDE.md` - Project instructions
- `AGENTS.md` - Agent development guide
- `CONTRIBUTING.md` - Contributor guide
- `ROADMAP.md` - Version roadmap
- `docs/user-guide/configuration.md` - Config reference (rewritten in v0.5.0)
- `docs/TROUBLESHOOTING.md` - Troubleshooting guide

**Decision**: Targeted fixes (fix broken parts, keep good content)

**Consistency Checks**:
- [ ] Version numbers match (0.5.0)
- [ ] CLI args match actual implementation
- [ ] Tool names match code
- [ ] Installation commands work
- [ ] Links to other docs are valid

### 7. Create SECURITY.md (P1 - New)

**Decision**: Full security policy

**Template**:
```markdown
# Security Policy

## Supported Versions
| Version | Supported |
|---------|-----------|
| 0.5.x   | ✅        |
| < 0.5   | ❌        |

## Reporting a Vulnerability
...
```

---

## Release Infrastructure

### 8. Version Synchronization (P0)

**Decision**: Single source of truth + CI enforcement

**Files with Version References**:
- `pyproject.toml` - **PRIMARY SOURCE**
- `src/zulipchat_mcp/__init__.py` - `__version__`
- `src/zulipchat_mcp/tools/system.py` - `server_info` version
- `CLAUDE.md` - Status section
- `AGENTS.md` - Status section
- `ROADMAP.md` - Current version
- `README.md` - Badge
- `server.json` - MCP registry metadata
- `CHANGELOG.md` - Release notes

**Automation**:
1. Create `scripts/bump-version.py` that updates all files
2. Add CI check in `.github/workflows/` that fails if versions mismatch

### 9. Git Tags & Releases (P1)

**Decision**: Major releases only (0.5, 0.6, 1.0)

**v0.5.0 Release**:
- Create GitHub Release with full changelog
- Include release notes summary
- Tag: v0.5.0

**Patches (0.5.1, 0.5.2)**:
- Git tags only
- No GitHub Release
- CHANGELOG.md is source of truth

### 10. PyPI Publishing (P1)

**Decision**: Beta classifier, professional metadata

**Current Issues (from PyPI research):**
- Classifier shows `Production/Stable` but should be `Beta`
- Missing `license-files` (PEP 639 requirement, deadline Feb 2026)
- Missing `Typing :: Typed` classifier
- Keywords could be expanded for discoverability

**pyproject.toml updates**:
```toml
[project]
license = "MIT"
license-files = ["LICENSE"]  # NEW: PEP 639 compliance

classifiers = [
    "Development Status :: 4 - Beta",  # Changed from 5 - Production/Stable
    "Intended Audience :: Developers",
    "Topic :: Communications :: Chat",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Typing :: Typed",  # NEW: We have type hints
]

keywords = [
    "mcp", "zulip", "chat", "ai", "assistant",
    "model-context-protocol", "messaging", "chatbot",
    "automation", "team-communication", "api"
]  # Expanded for discoverability

[project.urls]
Homepage = "https://github.com/akougkas/zulipchat-mcp"
Documentation = "https://github.com/akougkas/zulipchat-mcp/tree/main/docs"
Changelog = "https://github.com/akougkas/zulipchat-mcp/blob/main/CHANGELOG.md"
Issues = "https://github.com/akougkas/zulipchat-mcp/issues"
```

**Pre-publish validation**:
```bash
uv build && twine check dist/*
```

---

## Code Quality

### 11. Test Coverage (P2)

**Decision**: Quality over quantity, maintain >50%

**Current**: 69%
**Target**: Keep >50%, focus on meaningful tests

**Priority test areas**:
- Config loading with module-level state
- Tool error handling
- The config bug fix

### 12. Type Hints & Documentation (P3)

**Action Items**:
- [ ] Ensure all public APIs have type hints
- [ ] Add docstrings to undocumented functions
- [ ] Run mypy and fix any new issues

### 13. MCP Server Best Practices (P2 - from research)

**Critical**: Never use `print()` or stdout in STDIO-based MCP servers - it corrupts JSON-RPC messages.

**Verify**:
- [ ] All logging goes to stderr via `structlog` (already configured)
- [ ] No stray `print()` statements in tool code
- [ ] Debug output uses proper logging, not stdout

---

## Implementation Plan

### Phase 1: Critical Fix (This Session - Next)
1. Fix ConfigManager with module-level state pattern
2. Update server.py to call init_global_config()
3. Update all tools to use get_config()
4. Verify fix works with Claude MCP integration
5. Add test for config initialization

### Phase 2: README Overhaul (Same Session)
1. Update title to focus on categories
2. Restructure installation with progressive disclosure
3. Add standard badges (downloads, stars, last commit)
4. Update tool category table
5. Fix any broken links

### Phase 3: Documentation Sync (Same Session)
1. Launch 2-3 parallel agents for doc audits (staged waves)
2. Update version references to 0.5.0
3. Fix CLI arg references across all docs
4. Create SECURITY.md

### Phase 4: Release Prep (Same Session)
1. Run version bump script
2. Write comprehensive CHANGELOG.md entry
3. Create GitHub release
4. Publish to PyPI
5. Test installation: `uvx zulipchat-mcp --help`

---

## Parallel Agent Tasks (Staged Waves)

**Wave 1 (first)**:
- Agent 1: Tool Inventory - Count tools per category
- Agent 2: README Link Audit - Check all links

**Wave 2 (after Wave 1)**:
- Agent 3: Version Reference Scan - Find all version refs
- Agent 4: CLI Arg Verification - Compare docs vs code

**Wave 3 (final)**:
- Agent 5: code-simplifier for config.py fix

---

## Success Criteria for v0.5.0

- [ ] ConfigManager module-level state implemented
- [ ] All tools work with `--zulip-config-file`
- [ ] README focuses on 8 tool categories
- [ ] Progressive disclosure in installation section
- [ ] Standard badges added (downloads, stars, commit)
- [ ] All documentation links valid
- [ ] Version 0.5.0 consistent across all files
- [ ] CI version check added
- [ ] SECURITY.md created
- [ ] GitHub Release for v0.5.0 created
- [ ] PyPI package published with Beta classifier
- [ ] `uvx zulipchat-mcp --help` shows v0.5.0

---

## Post-v0.5.0 Roadmap

**Focus**: Community adoption

**Actions**:
- Blog post announcing v0.5.0
- Tutorial: "Building AI Agents with Zulip"
- Example integrations
- Outreach to Zulip community
- Monitor GitHub stars/issues for v1.0 signal

---

## Interview Data

All interview responses stored in:
`.claude/interviews/interview-zulipchat-v050-polishing-1737511200/`

**Rounds**:
1. Foundation & Strategy (config fix, success criteria, audience, versioning)
2. Documentation & Technical (tool display, install depth, stale docs, DI method)
3. Release Process & Quality (cadence, security, coverage, releases)
4. Future Roadmap (scope, v1.0 vision, maturity, badges)
5. Execution & Risk (agents, blockers, timeline, next priority)

---

*This plan is ready for execution in the next session. All decisions have been validated through user interview.*
