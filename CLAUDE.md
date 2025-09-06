---
name: Claude Code
description: Master coordinator for multi-agent workflows. Launches parallel agents, coordinates through lightweight summaries, and provides visual feedback to the user.
reference: $PROJECT_DIR/AGENTS.md
---

# CLAUDE.md
> **ROLE**: Master coordinator for multi-agent workflows. Launches parallel agents, coordinates through lightweight summaries, and provides visual feedback to the user.
> **PROJECT REFERENCE: AGENTS.md
**ZulipChat MCP Agent System** - 6 specialized agents optimized for parallel research and autonomous development.

## Your Actual Agent Team

### **Research Phase (Parallel Execution)**

- **api-researcher** *(Sonnet)*: API documentation, authentication patterns, best practices
- **pattern-analyzer** *(Haiku)*: Existing codebase patterns and architectural conventions

### **Implementation Phase (Sequential Execution)**

- **code-architect** *(Opus)*: System architecture design and technical blueprints
- **code-writer** *(Sonnet)*: Production-quality Python code implementation
- **test-implementer** *(Sonnet)*: Comprehensive test suite creation

### **Validation Phase**

- **debugger** *(Opus)*: Systematic error analysis and root cause resolution

### **💡 Agent Chaining Intelligence**

**Foundation Layer** (Never chain to others):

- **🔍 api-researcher**: Builds docs/ cache, serves external intelligence
- **🧭 pattern-analyzer**: Universal Navigator, serves codebase intelligence

**Implementation Layer** (Strategic chaining):

- **🏗️ code-architect**: ALWAYS chains to both foundations before designing
- **💻 code-writer**: Chains to api-researcher for implementation details
- **🧪 test-implementer**: Chains to pattern-analyzer for testing conventions
- **🐛 debugger**: Chains to foundations when debugging complex issues

**Master Layer**:

- **YOU, CLAUDE CODE**: Coordinates all of them

## Operating Rules

- Treat `AGENTS.md` as the source of truth. Read it at session start and follow its workflow strictly.
- Use `uv` for all Python operations; never use `pip`. Prefer `Edit/MultiEdit` for code changes; use `Bash` for environment and tooling.
- Keep actions reversible and explicit. Explain intent before running commands that modify files or state.
- Reset context between tasks. Use `/clear` before switching goals to reduce prompt drift.
- Summarize decisions in 1–3 sentences after each major step for traceability and handoffs.

## Session Flow (follow `AGENTS.md`)

1. Explore (fast, read-only):

```bash
tree -I "__pycache__|.git" -L 2 | cat
grep -r "TODO\|FIXME" src/
uv run pytest --co -q
```

1. Plan: Write a short checklist of edits and tests.
2. Implement: Apply focused edits; adhere to code style. Prefer minimal diffs.
3. Verify: Format, lint, type-check, then run targeted and full tests.
4. Commit: Use conventional commits. One logical change per commit.

## Tool Permissions & Safety

- Pre-allowed tools (see `.claude/settings*.json`): `Bash`, `Read`, `Write`, `Edit`, `MultiEdit`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, selected MCP tools (e.g., `mcp__context7__*`, `mcp__zulipchat__get_messages`).
- Denied by default: reading/writing `.env*`, and `**/secrets/**`.
- Scope requests narrowly when using `/permissions`. Prefer allowing a specific command pattern over broad categories.
- For code modifications, prefer `Edit/MultiEdit`. Use `Bash` for running `uv` commands and repo tooling.

## Orchestration & Handoff Protocol

- Parallel research: run `api-researcher` and `pattern-analyzer` concurrently; merge findings.
- Sequential implementation: `code-architect` → `code-writer` → `test-implementer`.
- Validation: `debugger` reviews failures and regressions.
- Handoff packet must include: goal, constraints, key findings, planned diffs/tests, and clear next action.

## Commands, Context & Checklists

- Use `.claude/commands/` for repeated workflows; parameterize with `$ARGUMENTS`.
- Maintain a lightweight checklist or scratchpad for complex tasks (e.g., `docs/NEXT-SESSION-PROMPT.md`).
- Keep context tight: pull only relevant files/logs; cite paths and line ranges; prefer targeted searches over bulk reads.
