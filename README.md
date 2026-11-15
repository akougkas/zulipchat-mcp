# ZulipChat MCP Server

<div align="center">

  <h3>Model Context Protocol server for Zulip Chat. Connect Claude Code, Codex, Clio Coder, OpenCode, Copilot, Antigravity CLI, Gemini CLI, and other MCP clients to Zulip.</h3>

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

Configure this command in your MCP client to let the assistant read and write
Zulip messages with the configured account.

Need a zuliprc? **Zulip Settings > Personal > Account & privacy > API key** — download the file, save it as `~/.zuliprc`.

Interactive onboarding:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

## What This Does

ZulipChat MCP bridges any MCP-compatible AI assistant (Claude Code, Gemini CLI, Cursor, Windsurf, etc.) to your Zulip workspace. The assistant can:

- **Send and read messages** — stream messages, DMs, replies, reactions
- **Search conversation history** — full-text search with filters for sender, stream, time range
- **Resolve people by name** — verify a unique recipient before sending; ambiguous names need clarification
- **Switch identities** — post as yourself or as a bot, in the same session
- **Monitor activity** — search recent messages, get stream info, check who's online
- **Bind sessions to Zulip topics** — give long-running agent sessions a stable control topic
- **Talk to local coding agents from Zulip** through the `zulipchat-mcp-agents` bridge, which pairs one Zulip bot per agent with an ACP agent on your machine ([Agent bots](docs/integrations/agent-bots.md))
- **Reuse dated snapshots** — short-lived message caches and rate-aware request admission reduce repeated API reads
- **Request approvals in-topic** — owner replies with `/approve REQUEST_ID` or `/deny REQUEST_ID` in the session topic; each decision names the request it answers
- **Load Agent Skills** — four packaged instructions for messaging, session control, notifications, and bounded work loops, available as local files and MCP Resources
- **Export agent packages** — native host configuration and skills, Claude's hook/plugin assets, or an Agent Plugins 1.0.0 package

### Agent setup

```bash
# Substitute another supported client as needed.
uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client clio-coder \
  --output-dir /absolute/path/to/project \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

Exports support `claude-code`, `codex`, `opencode`, `copilot`, `vscode`,
`antigravity-cli`, `clio-coder`, and `generic`. Add `--mode plugin` for a package.
For several Zulip organizations, export once per organization with
`--server-id zulipchat-<org>`; exports merge into one host configuration.
Account state lives under `~/.local/state/zulipchat-mcp/`. Host trust remains explicit;
Clio configures MCP execution separately from plugin content. See the
[capability matrix](docs/integrations/agent-skills.md),
[Clio guide](docs/integrations/clio-coder.md), and
[complete workflow](docs/integrations/agent-workflow.md).

For read-only access, add `--tool-profile read-only`: discovery and execution
both expose seven core reads or 22 extended reads. The default full profile
has 19 core tools and 53 extended. See [API coverage and efficiency](docs/developer-guide/zulip-api-proxy.md)
for cache freshness, rate limits and the boundary between message transport and
host execution. Hosts were tested through exported configuration and
fake-credential checks, not live sessions.

## Tool Set

**19 core tools** by default, **53** with `--extended-tools`. Hosts that search
tools lazily (Clio Coder, Claude Code) pay almost nothing for the larger set.

| Category | Core tools |
|----------|-------|
| **Messaging** | `send_message` (names, emails or IDs), `edit_message`, `get_message`, `add_reaction` |
| **Reading** | `search_messages`, `get_streams`, `get_stream_topics`, `manage_message_flags` |
| **Users** | `resolve_user`, `get_users` |
| **Agent bots** | `teleport_chat` (plus `ask_owner` inside agents the bridge launches) |
| **Agent sessions** | `register_agent`, `ensure_agent_session`, `agent_message`, `request_user_input`, `wait_for_response`, `poll_agent_events` |
| **System** | `server_info`, `switch_identity` |

### Talk to your agent from Zulip

`zulipchat-mcp-agents` runs on your machine and serves agent bots: one Zulip
Generic bot per coding agent that speaks the Agent Client Protocol (Clio Coder,
OpenCode, Goose, Gemini CLI, and Claude Code or Codex through their ACP
adapters).

```bash
uvx --from zulipchat-mcp zulipchat-mcp-agents add clio --owner-zuliprc ~/.zuliprc --cwd ~/projects
uvx --from zulipchat-mcp zulipchat-mcp-agents run
```

DM the bot, or mention it in a channel topic, and the bridge runs the agent in
a session for that conversation. Only the bot's owner, and user IDs you list,
are heard; anyone else gets no reply. The bridge connects out to Zulip and
opens no ports. From a running agent, `teleport_chat(agent, message,
session_id)` hands the conversation to that bot. The bridge has not yet been
tested live against Zulip. See [Agent bots](docs/integrations/agent-bots.md).

### Extended Mode

Need scheduled messages, reminders, topic resolution, read receipts, event queues, or file uploads?

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --extended-tools
```

Or via environment variable:
```bash
ZULIPCHAT_EXTENDED_TOOLS=1 uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

Extended mode adds: `cross_post_message`, `get_scheduled_messages`, `manage_scheduled_message`, `get_drafts`, `create_draft`, `edit_draft`, `delete_draft`, `register_events`, `get_events`, `listen_events`, `upload_file`, `manage_files`, `get_daily_summary`, `manage_user_mute`, `get_user`, `get_presence`, `get_user_groups`, and more.

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
uvx --from zulipchat-mcp zulipchat-mcp-hook \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Optional Claude package export for project-local hooks, skills, and subagents:
```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export \
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
| `--extended-tools` | Register all 53 tools instead of the 19-tool core set |
| `--tool-profile {full,read-only}` | Filter discovery and enforce read-only Zulip calls; default: `full` |
| `--ephemeral-state` | With `--tool-profile read-only`, keep local state in a temporary database removed at exit (for sandboxes with no writable state directory) |
| `--transport {stdio,http}` | Transport to serve on (default: `stdio`) |
| `--host HOST` | Bind host for HTTP transport (default: `127.0.0.1`) |
| `--port PORT` | Bind port for HTTP transport (default: `8000`) |
| `--auth-token TOKEN` | Bearer auth token for HTTP transport (or `ZULIPCHAT_HTTP_AUTH_TOKEN`) |
| `--allowed-host HOST` | Additional trusted HTTP hostname; repeat for multiple names |
| `--allowed-origin URL` | Additional trusted browser origin; repeat for multiple origins |
| `--unsafe` | Enable administrative tools (use with caution) |
| `--debug` | Enable debug logging |
| `--associate-existing-db` | Deliberately associate an unbound legacy database with the verified current account |

### Remote HTTP Transport

ZulipChat MCP supports stateless HTTP deployments under the MCP 2026-07-28 protocol:

```bash
# Run server over HTTP with bearer authentication
ZULIPCHAT_HTTP_AUTH_TOKEN=your-secret-token \
  uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --transport http --host 0.0.0.0 --port 8000 --allowed-host mcp.internal
```

Generate client integration snippets for remote HTTP connections:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate print --client claude-code --remote-url http://mcp.internal:8000/mcp --remote-token your-secret-token
```

HTTP startup requires a bearer token for non-loopback binds and validates Host and Origin headers. Configure `--allowed-host` for the hostname used by clients or a reverse proxy; terminate TLS at the proxy for remote connections. A token grants access to the configured Zulip account: deploy a separate instance per trusted account, rather than sharing it across unrelated users.

HTTP tools reject server-local file paths and `switch_identity`. Upload text with `file_content` or binary bytes with `file_content_base64`; download without `download_path` to obtain a URL. Use stdio for local file operations and runtime identity switching. Attachment deletion requires `--unsafe`.

Persistent state defaults to an account-scoped directory. An explicitly selected
`ZULIPCHAT_DB_PATH` is associated with the normalized realm and user/bot
principals; a different account cannot reuse it. Legacy state is left intact and
requires deliberate association. See [database migration](docs/user-guide/configuration.md#persistent-state-and-account-migration).

Agent sessions, approvals, listener cursors, and default background-task storage remain local state. Use a single instance for these workflows. Separate DuckDB paths avoid writer conflicts but do not share session data; ordinary round-robin routing across such replicas is not supported. Legacy HTTP clients may also retain transport sessions.

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

The assistant posts as **you** by default. Pass `as_bot=True` to `send_message` to post one message as the bot, or call `switch_identity` to change the default. Agent bots for the [bridge](docs/integrations/agent-bots.md) are separate Generic bots with their own zuliprc files.

## Real-World Examples

**"Catch me up on what happened in #engineering today"**
→ Assistant calls `search_messages` with stream + time filter, summarizes the thread.

**"Tell the team we're deploying at 3pm"**
→ Assistant calls `send_message` to #engineering with the announcement.

**"Who sent that message about the API migration?"**
→ Assistant calls `search_messages` with keywords, returns sender and context.

**"React with :thumbs_up: to Sarah's last message"**
→ Assistant calls `search_messages` with `sender="Sarah"`, then `add_reaction`.

**"DM Jaime that the PR is ready"**
→ Assistant calls `send_message(type="direct", to="Jaime", ...)`. One call; an ambiguous name returns candidates and sends nothing.

**"Continue this on Zulip, I'm heading out"**
→ Assistant calls `teleport_chat(agent="clio", message=..., session_id=...)`; the Clio bot DMs you and the bridge resumes the session when you reply.

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
├── agents/         # zulipchat-mcp-agents bridge (agent bots over ACP)
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
