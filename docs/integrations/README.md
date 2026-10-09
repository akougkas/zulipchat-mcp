# Integration Guide

Each page below includes copy-paste setup for one client.

- [Claude Code](claude-code.md)
- [Gemini CLI](gemini-cli.md)
- [Codex](codex.md)
- [OpenCode](opencode.md)
- [VS Code + GitHub Copilot](vscode-copilot.md)
- [GitHub Copilot CLI](copilot-cli.md)
- [Clio Coder](clio-coder.md)
- [Cursor](cursor.md)
- [Windsurf](windsurf.md)
- [Antigravity](antigravity.md)
- [Antigravity CLI](antigravity-cli.md)
- [Agent Skills and Plugins](agent-skills.md)
- [Topic-bound agent workflow](agent-workflow.md)
- [Generic MCP Client](generic.md)

## Shared baseline command

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Companion commands

The setup wizard, integration exporter, and Claude hook bridge are commands
provided by the `zulipchat-mcp` package. Always specify that package when invoking
these companion commands with `uvx`:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
uvx --from zulipchat-mcp zulipchat-mcp-integrate --help
uvx --from zulipchat-mcp zulipchat-mcp-hook --help
```

Without an explicit package source, `uvx` infers a package name from the command.
The companion commands are not separate distributions.

## Server flags

- `--zulip-bot-config-file ~/.zuliprc-bot`
- `--extended-tools`
- `--unsafe`
- `--debug`

## Package templates

Ready-to-use package templates are in `integrations/` at repository root.
