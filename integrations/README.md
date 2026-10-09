# Integration Packages

This directory contains ready-to-use integration templates for major MCP clients.

Each package includes:

- `package-metadata.json`: description, icon metadata, category tags, docs links
- Client-specific config template(s)
- Optional install helper script

Some packages also include richer scaffolds. Claude Code now ships:

- standalone `.claude/` assets with hooks, skills, and subagents
- a shareable Claude plugin template
- `uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client claude-code`
  for local export after publication (use `uv run` in this unpublished checkout)

Native configuration plus four Agent Skills can also be exported for Codex,
OpenCode, Copilot CLI, VS Code, Antigravity CLI, and Clio Coder. `portable/`
contains a schema-validated Agent Plugins 1.0.0 package. See the
[support matrix](../docs/integrations/agent-skills.md) for host-specific activation
and the distinction between plugin content and MCP execution trust.

## Clients

- `claude-code/`
- `gemini-cli/`
- `codex/`
- `opencode/`
- `vscode-copilot/`
- `cursor/`
- `windsurf/`
- `antigravity/`
- `generic/`
- `copilot-cli/`
- `antigravity-cli/`
- `clio-coder/`
- `portable/`

## Common runtime command

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```
