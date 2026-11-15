# Architecture Overview

ZulipChat MCP is organized around a compact default tool surface, optional extended tooling, and a DuckDB-backed agent control plane for Zulip-bound sessions.

## Top-level modules

```text
src/zulipchat_mcp/
├── server.py          # CLI entrypoint and tool registration mode
├── config.py          # zuliprc/env config loading + identity state
├── setup_wizard.py    # interactive setup helper
├── core/              # client wrapper, caching, security, command engine
├── tools/             # MCP tool implementations
├── services/          # listener/service manager, bot mention inbox
├── agents/            # zulipchat-mcp-agents: agent-bot bridge to ACP agents
└── utils/             # logging, metrics, duckdb managers
```

## Tool registration model

`server.py` always calls:

1. `register_core_tools(mcp)`
2. `register_extended_tools(mcp)` only when `--extended-tools` or `ZULIPCHAT_EXTENDED_TOOLS=1`

This produces:

- Core mode: 19 tools
- Extended mode: 53 tools
- `ask_owner` is added to either mode only when `ZULIPCHAT_AGENT_STATE` is set,
  that is, in the server the agent bridge injects into each agent it launches.

## Identity model

- Runtime identity is global (`user` or `bot`), managed in `config.py`.
- Default identity is `user`.
- `switch_identity` updates the active identity over stdio; HTTP rejects process-wide identity changes.
- Bot identity is available only when bot credentials are configured.

## Startup flow

1. Load compatible FastMCP 4 (`>=4.1.4,<5`, locked at 4.1.4) and MCP types 2
   (locked at 2.3.0), without protocol monkey patches.
2. Parse CLI flags (`--transport stdio|http`, `--host`, `--port`, `--auth-token`).
3. Initialize config manager.
4. Validate credentials (`zuliprc` or env fallback).
5. Set unsafe-mode context.
6. Resolve the effective account and associate its persistent state; initialize services.
7. Register FastMCP with SEP-2663 `TasksExtension`, SEP-2640 skills, and legacy skill Resources.
8. Register tools (core 19 or extended 53).
9. Leave user/stream caches lazy so startup does not contact Zulip.
10. Run FastMCP server (`stdio` or streamable `http`).

## Server-Side LLM Provider (`core/llm.py`)

MCP sampling is deprecated in the 2026-07-28 specification. This server has no LLM of its own: tools return compact data and the calling agent does the reasoning.

## Stateless HTTP Transport & Multi-Replica Caveat

`--transport http` enables streamable-HTTP serving. Requests are stateless and self-contained under the 2026-07-28 protocol, but agent sessions and task storage still require application-level state.

> **Single-instance workflows**: DuckDB storage (`zulipchat.duckdb`) is single-writer and the default task backend is local. Use one instance for agent sessions, approvals, and event listeners. Distinct DB paths avoid lock contention but do not share data, so round-robin routing across independent replicas is not supported. Legacy HTTP clients may retain transport sessions.

## Service behavior

- Listener services start through `ServiceManager`.
- The listener persists queue state and dispatches inbound topic messages into session events.
- Interactive MCP requests wait for queue readiness before announcing prompts.
  Queue replacement registers first, backfills bound topics from message
  watermarks, and deduplicates overlap with live events.
- Outbound echoes are recognized by message IDs, allowing owner replies when
  transport and owner use the same account.
- Owner policy is enforced at the session-topic boundary, not via AFK state.

## Agent control plane

- Stable agent profiles live in DuckDB and are keyed by owner + agent type + agent name.
- Agent sessions bind one Zulip topic to one agent runtime session.
- Requests and approvals are persisted separately from raw inbound events.
- Questions use `/reply REQUEST_ID ANSWER`; approvals use `/approve` or `/deny`
  with the request ID. Polling timeouts leave the request pending.
- Control-event polling excludes audit records by default and offers explicit
  acknowledgement for replay after an interrupted response.
- Databases are associated with the normalized realm and user/bot principals.
  Unbound legacy history requires explicit association; mismatches are rejected.
- `zulipchat-mcp-hook` bridges Claude Code lifecycle hooks into the same session model.

## Agent bridge

`zulipchat-mcp-agents` is a separate process, not part of the MCP server. It
serves agent bots: one Zulip Generic bot per local ACP agent, declared in
`~/.config/zulipchat-mcp/agents/<name>.toml` (`agents/config.py`). Per bot,
`agents/bridge.py` holds the bot's event queue through `BotMentionInbox` over
outbound HTTPS, maps each conversation to one ACP session, and launches the
agent on demand through `agents/acp.py`. Durable state lives in
`~/.local/state/zulipchat-mcp/agents/<name>.sqlite3` (`agents/store.py`):
conversation to session bindings, a turn journal for restart reporting, and
open permission requests and owner questions. The injected MCP server reads
the same file to implement `ask_owner`. See
[Agent bots](../integrations/agent-bots.md).

## Security-related boundaries

- `--unsafe` is off by default.
- Bearer token authentication required on non-loopback HTTP binds (`--auth-token` / `ZULIPCHAT_HTTP_AUTH_TOKEN`).
- Topic resolution goes through `resolve_topic`, which Clio exports classify as destructive.
- Agent emoji usage is validated against a fixed approved list.
