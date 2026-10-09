# ZulipChat MCP Documentation

ZulipChat MCP is a Model Context Protocol server for Zulip Chat. This branch
prepares v0.7.4; the latest published stable release is v0.7.3.

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
- [Clio Coder](integrations/clio-coder.md)
- [Agent Skills and Plugins](integrations/agent-skills.md)
- [Agent Workflow](integrations/agent-workflow.md)
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
- [Commands](api-reference/commands.md)
- [System](api-reference/system.md)

## Developer Docs

- [Architecture](developer-guide/architecture.md)
- [Zulip API Coverage and Efficiency](developer-guide/zulip-api-proxy.md)
- [Proposed Zulip Agent Control](developer-guide/zulip-agent-control-design.md)
- [Tool Categories](developer-guide/tool-categories.md)
- [Foundation Components](developer-guide/foundation-components.md)
- [Testing Guide](testing/README.md)
- [Live Clio Bot Mentions](testing/clio-bot-mentions.md)

## Tool Modes

- Default mode: 20 core tools.
- Extended mode: 60 total tools (`--extended-tools` or `ZULIPCHAT_EXTENDED_TOOLS=1`).
- `--tool-profile read-only`: nine core reads or 23 extended reads, with matching
  discovery and enforced call policy.

## Community and Security

- [Security Policy](../SECURITY.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Support](../SUPPORT.md)

## Historical Release Notes

- `docs/releases/` contains historical snapshots for earlier versions.
