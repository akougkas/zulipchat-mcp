# ZulipChat MCP Server

<div align="center">

  <h3>Give your AI assistant a Zulip account. Read messages, send replies, search history — through the Model Context Protocol.</h3>

  [![PyPI](https://img.shields.io/pypi/v/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![Downloads](https://img.shields.io/pypi/dm/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![GitHub stars](https://img.shields.io/github/stars/akougkas/zulipchat-mcp)](https://github.com/akougkas/zulipchat-mcp/stargazers)
  [![Python](https://img.shields.io/pypi/pyversions/zulipchat-mcp)](https://pypi.org/project/zulipchat-mcp/)
  [![License](https://img.shields.io/github/license/akougkas/zulipchat-mcp)](LICENSE)
  [![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)

  [Quick Start](#quick-start) · [Installation](#installation) · [Two-Tier Tools](#two-tier-tool-architecture) · [Examples](#real-world-examples) · [Contributing](CONTRIBUTING.md)
</div>

---

## Quick Start

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

That's it. Your AI assistant can now read and write Zulip messages.

Need a zuliprc? **Zulip Settings > Personal > Account & privacy > API key** — download the file, save it as `~/.zuliprc`.

## What This Does

ZulipChat MCP bridges any MCP-compatible AI assistant (Claude Code, Gemini CLI, Cursor, Windsurf, etc.) to your Zulip workspace. The assistant can:

- **Send and read messages** — stream messages, DMs, replies, reactions
- **Search conversation history** — full-text search with filters for sender, stream, time range
- **Resolve people by name** — "message Jaime" just works, no hunting for formal emails
- **Switch identities** — post as yourself or as a bot, in the same session
- **Monitor activity** — search recent messages, get stream info, check who's online

## Two-Tier Tool Architecture

v0.6.0 introduced a deliberate split: **19 core tools** by default, **~55 tools** when you need more.

### Core Mode (default)

The 19 tools that cover 95% of daily use:

| Category | Tools |
|----------|-------|
| **Messaging** | `send_message`, `edit_message`, `get_message`, `add_reaction` |
| **Search** | `search_messages`, `get_streams`, `get_stream_info`, `get_stream_topics` |
| **Users** | `resolve_user`, `get_users`, `get_own_user` |
| **Agent Comms** | `teleport_chat`, `register_agent`, `agent_message`, `request_user_input`, `wait_for_response` |
| **System** | `switch_identity`, `server_info`, `manage_message_flags` |

Why 19 instead of 55+? Fewer tools means faster tool selection, lower token overhead, and less confusion for the AI. Most tasks — sending messages, searching, reacting — only need the core set.

### Extended Mode

Need scheduled messages, event queues, file uploads, analytics, or advanced search?

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --extended-tools
```

Or via environment variable:
```bash
ZULIPCHAT_EXTENDED_TOOLS=1 uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

Extended mode adds: `toggle_reaction`, `cross_post_message`, `advanced_search`, `construct_narrow`, `get_scheduled_messages`, `manage_scheduled_message`, `register_events`, `get_events`, `listen_events`, `upload_file`, `manage_files`, `get_daily_summary`, `manage_user_mute`, `get_user`, `get_presence`, `get_user_groups`, and more.

## Installation

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
| `--extended-tools` | Register all ~55 tools instead of 19 |
| `--unsafe` | Enable administrative tools (use with caution) |
| `--debug` | Enable debug logging |

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
uv run pytest -q              # 556 tests, 60% coverage gate
uv run ruff check .           # Linting
uv run mypy src               # Type checking
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, and [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) for AI agent instructions.

## Architecture

```
src/zulipchat_mcp/
├── core/           # Client wrapper, identity, caching, security
├── tools/          # MCP tool implementations (two-tier registration)
├── services/       # Background listener, AFK watcher
├── utils/          # Logging, DuckDB persistence, metrics
└── config.py       # zuliprc-first configuration
```

Built on [FastMCP](https://github.com/jlowin/fastmcp) with async-first design, [DuckDB](https://duckdb.org) for agent state persistence, and smart user/stream caching for fast fuzzy resolution.

## Privacy

- **No data collection** — nothing leaves your machine except Zulip API calls
- **No telemetry** — zero analytics, tracking, or usage reporting
- **Local execution** — all processing happens on your hardware
- **Credentials stay local** — API keys are never logged or transmitted beyond your Zulip server

Full policy: [PRIVACY.md](PRIVACY.md)

## License

MIT — See [LICENSE](LICENSE)

## Links

- [Zulip API Documentation](https://zulip.com/api/)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Report Issues](https://github.com/akougkas/zulipchat-mcp/issues)
- [Discussions](https://github.com/akougkas/zulipchat-mcp/discussions)

---

<div align="center">
  <sub>Built for the Zulip community</sub>
</div>

<!-- mcp-name: io.github.akougkas/zulipchat -->
