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
├── services/          # listener/service manager
└── utils/             # logging, metrics, duckdb managers
```

## Tool registration model

`server.py` always calls:

1. `register_core_tools(mcp)`
2. `register_extended_tools(mcp)` only when `--extended-tools` or `ZULIPCHAT_EXTENDED_TOOLS=1`

This produces:

- Core mode: 20 tools
- Extended mode: 60 tools

## Identity model

- Runtime identity is global (`user` or `bot`), managed in `config.py`.
- Default identity is `user`.
- `switch_identity` updates the active identity over stdio; HTTP rejects process-wide identity changes.
- Bot identity is available only when bot credentials are configured.

## Startup flow

1. Load FastMCP 4.0.4 and MCP SDK/types 2.2.0 without protocol monkey patches.
2. Parse CLI flags (`--transport stdio|http`, `--host`, `--port`, `--auth-token`).
3. Initialize config manager.
4. Validate credentials (`zuliprc` or env fallback).
5. Set unsafe-mode context.
6. Initialize optional database/services.
7. Register FastMCP instance with SEP-2663 `TasksExtension`.
8. Register tools (core 20 or extended 60).
9. Leave user/stream caches lazy so startup does not contact Zulip.
10. Run FastMCP server (`stdio` or streamable `http`).

## Server-Side LLM Provider (`core/llm.py`)

MCP sampling is deprecated in the 2026-07-28 specification. This server follows the recommended direct-provider migration. AI analytics tools execute via a server-side Anthropic provider (`core/llm.py`) configured with `ANTHROPIC_API_KEY`. When unconfigured, tools report `llm_unavailable: true` and return raw structured summaries so calling agents can reason over data directly.

## Stateless HTTP Transport & Multi-Replica Caveat

`--transport http` enables streamable-HTTP serving. Requests are stateless and self-contained under the 2026-07-28 protocol, but agent sessions and task storage still require application-level state.

> **Single-instance workflows**: DuckDB storage (`zulipchat.duckdb`) is single-writer and the default task backend is local. Use one instance for agent sessions, approvals, and event listeners. Distinct DB paths avoid lock contention but do not share data, so round-robin routing across independent replicas is not supported. Legacy HTTP clients may retain transport sessions.

## Service behavior

- Listener services start through `ServiceManager`.
- The listener persists queue state and dispatches inbound topic messages into session events.
- Owner policy is enforced at the session-topic boundary, not via AFK state.

## Agent control plane

- Stable agent profiles live in DuckDB and are keyed by owner + agent type + agent name.
- Agent sessions bind one Zulip topic to one agent runtime session.
- Requests and approvals are persisted separately from raw inbound events.
- `zulipchat-mcp-hook` bridges Claude Code lifecycle hooks into the same session model.

## Security-related boundaries

- `--unsafe` is off by default.
- Bearer token authentication required on non-loopback HTTP binds (`--auth-token` / `ZULIPCHAT_HTTP_AUTH_TOKEN`).
- Destructive topic delete path is guarded in `agents_channel_topic_ops`.
- Agent emoji usage is validated against a fixed approved list.
