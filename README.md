# ZulipChat MCP Server

<div align="center">

  <h3>Model Context Protocol server for Zulip Chat. Connect Claude Code, Gemini CLI, Codex, Cursor, Windsurf, VS Code Copilot, and other MCP clients to Zulip.</h3>

  [![PyPI](https://img.shields.io/pypi/v/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![CI](https://github.com/akougkas/zulipchat-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/akougkas/zulipchat-mcp/actions/workflows/ci.yml)
  [![Publish](https://github.com/akougkas/zulipchat-mcp/actions/workflows/publish.yml/badge.svg)](https://github.com/akougkas/zulipchat-mcp/actions/workflows/publish.yml)
  [![Coverage Gate](https://img.shields.io/badge/coverage%20gate-60%25-blue)](https://github.com/akougkas/zulipchat-mcp/actions/workflows/ci.yml)
  [![Downloads](https://img.shields.io/pypi/dm/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![GitHub stars](https://img.shields.io/github/stars/akougkas/zulipchat-mcp)](https://github.com/akougkas/zulipchat-mcp/stargazers)
  [![Python](https://img.shields.io/pypi/pyversions/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![License](https://img.shields.io/github/license/akougkas/zulipchat-mcp)](LICENSE)
  [![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)

  [Quick Start](#quick-start) · [Setup Wizard](docs/user-guide/setup-wizard.md) · [Integrations](docs/integrations/README.md) · [Two-Tier Tools](#two-tier-tool-architecture) · [Contributing](CONTRIBUTING.md)
</div>

---

## Quick Start

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

That's it. Your AI assistant can now read and write Zulip messages.

Need a zuliprc? **Zulip Settings > Personal > Account & privacy > API key** — download the file, save it as `~/.zuliprc`.

Interactive onboarding:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

## What This Does

ZulipChat MCP bridges any MCP-compatible AI assistant (Claude Code, Gemini CLI, Cursor, Windsurf, etc.) to your Zulip workspace. The assistant can:

- **Send and read messages** — stream messages, DMs, replies, reactions
- **Search conversation history** — full-text search with filters for sender, stream, time range
- **Resolve people by name** — "message Jaime" just works, no hunting for formal emails
- **Switch identities** — post as yourself or as a bot, in the same session
- **Monitor activity** — search recent messages, get stream info, check who's online
- **Bind sessions to Zulip topics** — give long-running agent sessions a stable control topic
- **Request approvals in-topic** — owner replies with `approve` / `deny` in the session topic

## Two-Tier Tool Architecture

v0.6.0 introduced a deliberate split: **20 core tools** by default, **60 tools** when you need more.

### Core Mode (default)

The 20 tools that cover most daily use:

| Category | Tools |
|----------|-------|
| **Messaging** | `send_message`, `edit_message`, `get_message`, `add_reaction` |
| **Search** | `search_messages`, `get_streams`, `get_stream_info`, `get_stream_topics` |
| **Users** | `resolve_user`, `get_users`, `get_own_user` |
| **Agent Comms** | `teleport_chat`, `register_agent`, `ensure_agent_session`, `agent_message`, `request_user_input`, `wait_for_response` |
| **System** | `switch_identity`, `server_info`, `manage_message_flags` |

Why 20 instead of 60? Fewer tools means faster tool selection, lower token overhead, and less confusion for the AI. Most tasks — sending messages, searching, reacting, and binding an agent session to Zulip — only need the core set.

### Extended Mode

Need scheduled messages, event queues, file uploads, analytics, or advanced search?

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --extended-tools
```

Or via environment variable:
```bash
ZULIPCHAT_EXTENDED_TOOLS=1 uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

Extended mode adds: `toggle_reaction`, `cross_post_message`, `advanced_search`, `construct_narrow`, `get_scheduled_messages`, `manage_scheduled_message`, `get_drafts`, `create_draft`, `edit_draft`, `delete_draft`, `register_events`, `get_events`, `listen_events`, `upload_file`, `manage_files`, `get_daily_summary`, `manage_user_mute`, `get_user`, `get_presence`, `get_user_groups`, and more.

## Installation

Full per-client setup guide: [docs/integrations/README.md](docs/integrations/README.md)

### Claude Code

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

With dual identity (you + a bot):
```bash
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Optional Claude hook bridge for lifecycle and approval routing:
```bash
uvx zulipchat-mcp-hook \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Optional Claude package export for project-local hooks, skills, and subagents:
```bash
uvx zulipchat-mcp-integrate export \
  --client claude-code \
  --mode standalone \
  --output-dir . \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

### Gemini CLI

Add to `~/.gemini/settings.json` under `mcpServers`:

```json
{
  "zulipchat": {
    "command": "uvx",
    "args": ["zulipchat-mcp", "--zulip-config-file", "/path/to/.zuliprc"]
  }
}
```

### Claude Desktop / Cursor / Any MCP Client

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp", "--zulip-config-file", "/path/to/.zuliprc"]
    }
  }
}
```

### Configuration Options

| Option | Description |
|--------|-------------|
| `--zulip-config-file PATH` | Path to your zuliprc file |
| `--zulip-bot-config-file PATH` | Bot zuliprc for dual identity |
| `--extended-tools` | Register all 60 tools instead of the 20-tool core set |
| `--transport {stdio,http}` | Transport to serve on (default: `stdio`) |
| `--host HOST` | Bind host for HTTP transport (default: `127.0.0.1`) |
| `--port PORT` | Bind port for HTTP transport (default: `8000`) |
| `--auth-token TOKEN` | Bearer auth token for HTTP transport (or `ZULIPCHAT_HTTP_AUTH_TOKEN`) |
| `--unsafe` | Enable administrative tools (use with caution) |
| `--debug` | Enable debug logging |

### Remote HTTP Transport

ZulipChat MCP supports stateless HTTP deployments under the MCP 2026-07-28 protocol:

```bash
# Run server over HTTP with bearer authentication
ZULIPCHAT_HTTP_AUTH_TOKEN=your-secret-token \
  uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --transport http --host 0.0.0.0 --port 8000
```

Generate client integration snippets for remote HTTP connections:

```bash
uvx zulipchat-mcp-integrate print --client claude-code --remote-url http://mcp.internal:8000/mcp --remote-token your-secret-token
```

> **Note on Multi-Replica Deployments**: DuckDB state persistence is single-writer. When deploying multiple HTTP replicas, ensure each instance points to a distinct DuckDB path or run a single-instance deployment.

### AI Analytics & LLM Provider

AI-powered analytics tools (`analyze_stream_with_llm`, `analyze_team_activity_with_llm`, `intelligent_report_generator`) execute using a server-side Anthropic LLM provider:

- Set `ANTHROPIC_API_KEY` on the server process for LLM generation.
- Optionally set `ANTHROPIC_MODEL` to override the default model (`claude-opus-5`).
- Without an API key, analytics tools return structured data summaries with `llm_unavailable: true` so your client assistant can analyze the data directly.

### More clients

Dedicated setup pages:

- [Gemini CLI](docs/integrations/gemini-cli.md)
- [Codex](docs/integrations/codex.md)
- [OpenCode](docs/integrations/opencode.md)
- [VS Code + GitHub Copilot](docs/integrations/vscode-copilot.md)
- [Cursor](docs/integrations/cursor.md)
- [Windsurf](docs/integrations/windsurf.md)
- [Antigravity](docs/integrations/antigravity.md)
- [Generic MCP](docs/integrations/generic.md)

## Dual Identity

Configure both a user and a bot zuliprc to let your assistant switch between identities mid-session:

```bash
uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

The assistant posts as **you** by default. Call `switch_identity` to post as the bot — useful for automated notifications, agent-to-agent communication, or keeping human vs. bot messages distinct.

## Real-World Examples

**"Catch me up on what happened in #engineering today"**
→ Assistant calls `search_messages` with stream + time filter, summarizes the thread.

**"Tell the team we're deploying at 3pm"**
→ Assistant calls `send_message` to #engineering with the announcement.

**"Who sent that message about the API migration?"**
→ Assistant calls `search_messages` with keywords, returns sender and context.

**"React with :thumbs_up: to Sarah's last message"**
→ Assistant calls `resolve_user` ("Sarah"), `search_messages` (sender), then `add_reaction`.

**"DM Jaime that the PR is ready"**
→ Assistant calls `teleport_chat` with fuzzy name resolution — no email needed.

## Development

```bash
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync
uv run zulipchat-mcp --zulip-config-file ~/.zuliprc
```

Run checks:
```bash
uv run pytest -q              # full test suite, 60% coverage gate
uv run ruff check .           # Linting
uv run mypy src               # Type checking
```

For packaging, dependency, FastMCP, or startup changes, run the release smoke:

```bash
uv build
scripts/pre_release_smoke.sh --version X.Y.Z --allow-dirty
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, and [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) for AI agent instructions.

## Architecture

```
src/zulipchat_mcp/
├── core/           # Client wrapper, identity, caching, security
├── tools/          # MCP tool implementations (two-tier registration)
├── services/       # Background listener and session event routing
├── utils/          # Logging, DuckDB persistence, metrics
└── config.py       # config loading (zuliprc + environment fallback)
```

Built on [FastMCP](https://github.com/PrefectHQ/fastmcp) with async-first design, [DuckDB](https://duckdb.org) for agent state persistence, and smart user/stream caching for fast fuzzy resolution.

## Privacy

- **No data collection** — nothing leaves your machine except Zulip API calls
- **No telemetry** — zero analytics, tracking, or usage reporting
- **Local execution** — all processing happens on your hardware
- **Credentials stay local** — API keys are never logged or transmitted beyond your Zulip server

Full policy: [PRIVACY.md](PRIVACY.md)

## License

MIT — See [LICENSE](LICENSE)

## Links

- [Documentation Index](docs/README.md)
- [Support](SUPPORT.md)
- [Security Policy](SECURITY.md)
- [Zulip API Documentation](https://zulip.com/api/)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Report Issues](https://github.com/akougkas/zulipchat-mcp/issues)
- [Discussions](https://github.com/akougkas/zulipchat-mcp/discussions)

---

<div align="center">
  <sub>Built for the Zulip community</sub>
</div>

<!-- mcp-name: io.github.akougkas/zulipchat -->
