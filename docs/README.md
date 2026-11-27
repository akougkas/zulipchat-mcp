# ZulipChat MCP Documentation

ZulipChat MCP is a Model Context Protocol server for Zulip Chat. These docs
describe v0.8.3, the latest published release.

## Start Here

- [Quick Start](user-guide/quick-start.md)
- [Installation](user-guide/installation.md)
- [Configuration](user-guide/configuration.md)
- [Setup Wizard](user-guide/setup-wizard.md)
- [Troubleshooting](TROUBLESHOOTING.md)

## Integrations

- [Integration Index](integrations/README.md)
- [Claude Code](integrations/claude-code.md)
- [Gemini CLI](integrations/gemini-cli.md)
- [Codex](integrations/codex.md)
- [OpenCode](integrations/opencode.md)
- [VS Code + GitHub Copilot](integrations/vscode-copilot.md)
- [Copilot CLI](integrations/copilot-cli.md)
- [PanCode](integrations/pancode.md)
- [Agent Skills and Plugins](integrations/agent-skills.md)
- [Agent Bots](integrations/agent-bots.md): talk to local coding agents from Zulip
- [Cursor](integrations/cursor.md)
- [Windsurf](integrations/windsurf.md)
- [Antigravity](integrations/antigravity.md)
- [Antigravity CLI](integrations/antigravity-cli.md)
- [Generic MCP Client](integrations/generic.md)

## API Reference

- [Messaging](api-reference/messaging.md)
- [Streams](api-reference/streams.md)
- [Users](api-reference/users.md)
- [Search](api-reference/search.md)
- [Events](api-reference/events.md)
- [Files](api-reference/files.md)
- [Agents](api-reference/agents.md)
- [System](api-reference/system.md)

## Developer Docs

- [Architecture](developer-guide/architecture.md)
- [Zulip API Coverage and Efficiency](developer-guide/zulip-api-proxy.md)
- [Tool Categories](developer-guide/tool-categories.md)
- [Foundation Components](developer-guide/foundation-components.md)
- [Testing Guide](testing/README.md)

## Tool Modes

- Default mode: 13 core tools.
- Extended mode: 53 total tools (`--extended-tools` or `ZULIPCHAT_EXTENDED_TOOLS=1`).
- Agents launched by `zulipchat-mcp-agents` also get `ask_owner`.
- `--tool-profile read-only`: seven core reads or 21 extended reads, with matching
  discovery and enforced call policy.

## Community and Security

- [Security Policy](../SECURITY.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Support](../SUPPORT.md)

## Historical Release Notes

- `docs/releases/` contains historical snapshots for earlier versions.
