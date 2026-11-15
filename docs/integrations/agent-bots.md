# Agent bots

`zulipchat-mcp-agents` lets the owner of a Zulip account talk to coding agents
running on their own machine. Each agent gets its own Zulip Generic bot, called
an agent bot. The owner DMs the bot, or mentions it in a channel topic, and a
local bridge relays the conversation to the agent over the
[Agent Client Protocol](https://agentclientprotocol.com) (ACP).

Status: new in v0.8.0, which is not yet released. The bridge is tested with a
fake ACP agent, and real Clio Coder, OpenCode and Goose processes were probed
for start, session creation and resume (no prompts). It has not yet been
exercised live against a Zulip server.

## How it works

- **One bot per agent.** An agent bot is declared in
  `~/.config/zulipchat-mcp/agents/<name>.toml`, which names the bot's zuliprc
  and the command that starts the agent in ACP mode.
- **No inbound ports.** For each bot, the bridge holds the bot's Zulip event
  queue over outbound HTTPS. It receives direct messages to the bot and
  @-mentions of the bot in every channel the bot can read. On first start it
  begins from the newest message; older messages are never replayed as work.
- **One conversation, one session.** A DM with the bot (keyed by its
  participants) or one channel topic is one ACP session. In a topic, a message
  must mention the bot to start a turn.
- **On demand.** The agent process starts when a conversation needs it and
  stops after `idle_minutes` without work. The next message resumes the same
  session through `session/resume`, or `session/load`, when the agent supports
  either; otherwise a fresh session starts.
- **Owner only.** The bridge hears the bot's owner in Zulip (`bot_owner_id`)
  and the user IDs listed in `allow`. Messages from anyone else are dropped
  without a reply.
- **Turns.** The bridge reacts with :eyes:, shows a typing indicator while the
  agent works, and posts the agent's final answer as Markdown, split into
  several messages when long. Messages that arrive during a turn are sent
  together as the next prompt.
- **Permissions.** The agent runs under its own native permission policy. The
  bridge does not offer it ACP file system or terminal capabilities. When the
  agent sends an ACP permission request, the bridge posts it in the
  conversation as `Permission request ID`. Answer `yes` or `no` (or
  `/approve ID`, `/deny ID`). No answer within `question_minutes` means no.
- **Restarts.** A journal records turns in flight. After a crash or restart the
  bridge tells each affected conversation that the earlier message may be only
  partly done; it never replays it.

Per-bot state lives in `~/.local/state/zulipchat-mcp/agents/` (honoring
`XDG_STATE_HOME`): `<name>.sqlite3` holds conversation bindings, the turn
journal and open questions; `<name>-inbox.sqlite3` holds the event snapshot.

## Set up a bot

Create a Generic bot you own and declare it in one step. The owner zuliprc must
belong to a human, non-guest account:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-agents add clio \
  --owner-zuliprc ~/.zuliprc --cwd ~/projects
```

This creates the bot through `POST /bots`, writes its key to
`~/.config/zulipchat-mcp/agents/clio.zuliprc` (mode 0600, never overwritten),
and writes `clio.toml` beside it. To use an existing Generic bot instead, pass
`--bot-zuliprc PATH`; the bot must have an owner in Zulip, and that owner is
who the bridge hears. `--full-name` and `--short-name` name a new bot.

Known names fill in the launch command; any other name needs `--command`:

| Name | Command |
| --- | --- |
| `clio` | `clio-coder acp` |
| `opencode` | `opencode acp` |
| `goose` | `goose acp` |
| `gemini` | `gemini --acp` |
| `claude` | `npx -y @agentclientprotocol/claude-agent-acp` |
| `codex` | `npx -y @agentclientprotocol/codex-acp` |

```bash
uvx --from zulipchat-mcp zulipchat-mcp-agents add reviewer \
  --command "my-agent --acp" --bot-zuliprc ~/.zuliprc-reviewer \
  --cwd ~/projects/app --allowed-dir ~/projects
```

Then validate and serve:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-agents list
uvx --from zulipchat-mcp zulipchat-mcp-agents run            # every declared bot
uvx --from zulipchat-mcp zulipchat-mcp-agents run --agent clio
```

`list` exits non-zero if any file is invalid and notes commands missing from
`PATH`. `run` serves until SIGINT or SIGTERM; `--debug` raises the log level.
From a source checkout, use `uv run zulipchat-mcp-agents`.

To keep the bridge running, `service` prints a systemd user unit:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-agents service \
  > ~/.config/systemd/user/zulipchat-mcp-agents.service
systemctl --user daemon-reload
systemctl --user enable --now zulipchat-mcp-agents
```

## Agent file

```toml
# ~/.config/zulipchat-mcp/agents/clio.toml
zuliprc = "~/.config/zulipchat-mcp/agents/clio.zuliprc"
command = ["clio-coder", "acp"]
cwd = "~/projects"
allowed_dirs = ["~/projects"]
allow = []
idle_minutes = 30
question_minutes = 30
zulip_tools = true
env = {}
```

| Key | Default | Meaning |
| --- | --- | --- |
| `zuliprc` | required | The bot's own zuliprc. |
| `command` | required | Non-empty list: the agent's ACP launch command. |
| `cwd` | `~` | Default workspace; must lie inside `allowed_dirs`. |
| `allowed_dirs` | `[cwd]` | Directories `/cwd` and `teleport_chat` may select. |
| `allow` | `[]` | Numeric Zulip user IDs heard besides the bot's owner. |
| `idle_minutes` | `30` | Stop an idle agent process; its session resumes later. |
| `question_minutes` | `30` | Lifetime of permission requests and `ask_owner` questions. |
| `zulip_tools` | `true` | Give the agent this server's Zulip tools, acting as the bot. |
| `env` | `{}` | Extra environment variables (strings) for the agent. |

File names are the agent names: lowercase, starting with a letter, at most 32
characters of `a-z`, `0-9`, `-` and `_`. Unknown keys are rejected. Paths expand
`~` and environment variables. The directory honors `XDG_CONFIG_HOME`.

`allowed_dirs` limits where the bridge starts the agent. It does not sandbox the
agent; file access is governed by the agent's own permission policy.

## The agent's environment

The agent inherits the bridge's environment with every variable whose name
starts with `ZULIP` removed, so it never sees the owner's Zulip credentials,
plus the file's `env`. With `zulip_tools = true`, the bridge passes the agent an
MCP server over ACP `mcpServers`: this package's server, run with the bot's
zuliprc. The agent's Zulip tools therefore read and post as the bot. That server
also registers `ask_owner`:

```text
ask_owner(question, question_id=None, wait_seconds=300)
```

It posts the question in the agent's own conversation and waits up to
`wait_seconds` (at most 840). The owner's next message there is the answer;
it does not start a new turn. A timeout returns `status="pending"` with the
`question_id`; call again with it to keep waiting. After `question_minutes` the
question expires.

## Commands in Zulip

Send these in the conversation (in a topic, mention the bot):

| Command | Effect |
| --- | --- |
| `/status` | Whether the agent is working, running or stopped; session, workspace and queue. |
| `/cancel` | Cancel the current turn. |
| `/new` | Close the agent; the next message starts a fresh session. |
| `/cwd PATH` | Switch workspace to a directory inside `allowed_dirs`; the next message starts there. |
| `/approve ID`, `/deny ID` | Answer a specific permission request. |

Any other command shows this list.

## Hand a session to Zulip

From an agent running elsewhere with this MCP server configured over stdio:

```text
teleport_chat(agent, message, session_id=None, cwd=None)
```

The agent bot named `agent` DMs its owner `message`. When the owner replies in
that DM, the bridge resumes `session_id` if given and supported, and otherwise
starts a fresh session in `cwd` (default: the file's `cwd`, which must lie in
`allowed_dirs`). The bridge must be running to answer. Errors are listed in
the [Agents API](../api-reference/agents.md#agent-bots).

## Privacy

- Zulip organization administrators can read any bot's API key, and with it
  everything the bot can read. Never send secrets through Zulip.
- Direct messages with the bot, or a private channel holding only the owner
  and the bot, are the private surfaces. In a shared channel, the agent's
  answers are visible to every member.
- The agent's Zulip tools act as the bot, so they reach whatever the bot can
  read, including channels it is subscribed to.

## Known limitations

- Goose hangs when asked to resume a session ID it does not know. The bridge
  gives up after its request timeout and starts a fresh session.
- `teleport_chat` works over stdio only; HTTP deployments refuse it.
- Run one bridge per bot. Two bridges for the same bot on different machines
  would both answer.
