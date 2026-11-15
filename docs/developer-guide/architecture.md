# Architecture Overview

The package ships two programs with one job each. `zulipchat-mcp` is an MCP
server: a tool surface for an agent that is already running. It never listens
for messages and keeps no conversation state. `zulipchat-mcp-agents` is the
bridge: the one long-running process that listens to Zulip and wakes local
coding agents. They meet at two points, described under [Agent bridge](#agent-bridge).

## Top-level modules

```text
src/zulipchat_mcp/
├── server.py          # MCP server entry point and tool registration mode
├── config.py          # zuliprc/env config loading + identity state
├── setup_wizard.py    # interactive setup helper
├── core/              # client wrapper, caching, security, tool contract, skills
├── tools/             # MCP tool implementations
├── services/          # the bot message queue the bridge drains
├── agents/            # zulipchat-mcp-agents: agent-bot bridge to ACP agents
├── integrations/      # host configuration and plugin exports
└── utils/             # logging, redaction, metrics
```

## Tool registration model

`server.py` always calls:

1. `register_core_tools(mcp)`
2. `register_extended_tools(mcp)` only when `--extended-tools` or `ZULIPCHAT_EXTENDED_TOOLS=1`

This produces:

- Core mode: 13 tools
- Extended mode: 45 tools
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
   Flags of the control plane removed in 0.8.0 (`--enable-listener`,
   `--associate-existing-db`, `--mention-allow`) are accepted and ignored with
   a warning.
3. Initialize config manager and validate credentials (`zuliprc` or env fallback).
4. Set unsafe-mode context.
5. Resolve the effective account and point the shared read cache at
   `$XDG_STATE_HOME/zulipchat-mcp/accounts/<fingerprint>/cache`, unless
   `--ephemeral-state` keeps it in memory.
6. Register FastMCP with SEP-2663 `TasksExtension`, SEP-2640 skills, and legacy skill Resources.
7. Register tools (core 13 or extended 45).
8. Leave user/stream caches lazy so startup does not contact Zulip.
9. Run FastMCP server (`stdio` or streamable `http`).

## No server-side LLM

MCP sampling is deprecated in the 2026-07-28 specification. This server has no LLM of its own: tools return compact data and the calling agent does the reasoning.

## Stateless HTTP transport

`--transport http` enables streamable-HTTP serving. Requests are self-contained
under the 2026-07-28 protocol. The default background-task backend is local to
one process, so a task's follow-up requests must reach the instance that
started it. Legacy HTTP clients may retain transport sessions.

## Agent bridge

`zulipchat-mcp-agents` is a separate process, not part of the MCP server: an
MCP server lives as long as its host session, while the bridge must hold the
bots' event queues all the time. It serves agent bots: one Zulip Generic bot
per local ACP agent, declared in `~/.config/zulipchat-mcp/agents/<name>.toml`
(`agents/config.py`). Per bot, `agents/bridge.py` holds the bot's event queue
over outbound HTTPS and drains a durable message queue,
`BotMentionInbox` in `services/bot_mentions.py` (`<name>-inbox.sqlite3`).
Rows move `new` → `queued` (a prompt, keyed by conversation) → `running`
(one turn) and are deleted when handled; rows still `running` at start are
reported as cut off and never replayed. The bridge holds the queue's lease for
its life, so one process serves a bot. It maps each conversation to one ACP
session and launches the agent on demand through `agents/acp.py`. Bridge state
lives in `~/.local/state/zulipchat-mcp/agents/<name>.sqlite3`
(`agents/store.py`): conversation to session bindings and open permission
requests and owner questions. `agents/service.py` installs the
bridge as a systemd user unit or launchd agent.

The two programs meet at two points, both through that state file:

- The bridge passes each agent this MCP server, run with the bot's zuliprc and
  `--tool-profile ask-owner`. Its `ask_owner` tool posts in the agent's own
  conversation and reads the answer the bridge records.
- `teleport_chat` (and `zulipchat-mcp-agents teleport`) binds the owner's DM
  with a bot to a session, so the bridge resumes it on the owner's reply.

See [Agent bots](../integrations/agent-bots.md).

## Security-related boundaries

- `--unsafe` is off by default.
- Bearer token authentication required on non-loopback HTTP binds (`--auth-token` / `ZULIPCHAT_HTTP_AUTH_TOKEN`).
- Topic resolution goes through `resolve_topic`, which Clio exports classify as destructive.
- Agent emoji usage is validated against a fixed approved list.
- The bridge hears only the bot's owner (by user ID) and listed user IDs, and
  answers permission requests only from what it read in Zulip itself.
