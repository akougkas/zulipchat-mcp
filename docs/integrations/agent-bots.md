# Agent bots

`zulipchat-mcp-agents` lets the owner of a Zulip account talk to coding agents
running on their own machine. Each agent gets its own Zulip Generic bot, called
an agent bot. The owner DMs the bot, or mentions it in a channel topic, and a
local bridge relays the conversation to the agent over the
[Agent Client Protocol](https://agentclientprotocol.com) (ACP).

Status: new in v0.8.0, which is not yet released. The bridge is tested with a
fake ACP agent and a mocked Zulip client. Real Clio Coder and Claude Code
(`claude-agent-acp`) turns were run through the bridge with a mocked Zulip:
prompts, resume, Clio interviews and the progress message. OpenCode and Goose
were probed for start, session creation and resume. Live use against a Zulip
server has begun with Clio Coder.

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
  without a reply. On its first run the bridge pairs with that owner. An
  organization administrator can reassign a bot, so the bridge refuses to
  start when Zulip reports a different owner, checks again every five minutes,
  and stops serving everyone when the owner changes. After changing the owner
  yourself, start once with `zulipchat-mcp-agents run --accept-owner`.
- **Turns.** The bridge reacts with :eyes:, shows a typing indicator while the
  agent works, and posts the agent's final answer as Markdown, split into at
  most five messages when long. Messages that arrive during a turn are sent
  together as the next prompt. Mentions in anything the bridge posts for the
  agent are made silent, so an answer notifies nobody but the conversation.
- **Progress.** A turn still running after 20 seconds gets one status message,
  edited in place every 10 seconds: elapsed time, tool call count, the current
  tool call and the agent's plan. It ends as `Finished in …`. The final answer
  is a new message, so it is the one that notifies. If the realm refuses the
  bot's edits, the status stays as first posted; past an edit time limit, a
  new status message continues.
- **Permissions.** The agent runs under its own native permission policy. The
  bridge does not offer it ACP file system or terminal capabilities. When the
  agent sends an ACP permission request, the bridge posts it in the
  conversation as `Permission request ID`, with the command or paths involved
  and, from Clio, its consequence lines. Up to 6000 characters of a command
  are shown, and the request says so when there is more. Answer with a
  message that is only `yes` or `no` (or `/approve ID`, `/deny ID`), or react
  👍 or 👎 (✅ and ❌ also work) on the request. Any other message leaves it
  open. No answer within `question_minutes` means no. A request the agent
  withdraws, or that a `/cancel` ends, is closed in the conversation, so the
  next message starts a turn again.
- **Clio Coder interviews.** The bridge tells Clio a person is attending
  (`clio-coder/interviews` and `clio-coder/workerPermissions` in
  `clientCapabilities._meta`). Clio's `ask_user` questions then arrive as
  `Question ID`, one at a time; reply with an option's number or label (several,
  comma-separated, when it allows more than one) or in your own words. Workers'
  permission requests arrive like any other permission request.
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
| `claude` | `claude-agent-acp` |
| `codex` | `npx -y @agentclientprotocol/codex-acp` |

`claude` needs `npm i -g @agentclientprotocol/claude-agent-acp`. The adapter
bundles its own Claude Code, and the API refuses models to an outdated one, so
upgrade the package when Claude Code moves. An unpinned `npx` would resolve to
whatever old copy is installed globally.

The bridge passes `--permission-timeout` to `clio-coder acp` so Clio waits for
a permission answer or an interview as long as the question stays open in Zulip
(`question_minutes`). Clio's own default is two minutes.

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
zulip_tools = "ask"
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
| `zulip_tools` | `"ask"` | `"ask"`: only `ask_owner`. `true`: every tool of this server, acting as the bot. `false`: none. |
| `env` | `{}` | Extra environment variables (strings) for the agent. |

File names are the agent names: lowercase, starting with a letter, at most 32
characters of `a-z`, `0-9`, `-` and `_`. Unknown keys are rejected. Paths expand
`~` and environment variables. The directory honors `XDG_CONFIG_HOME`.

`allowed_dirs` limits where the bridge starts the agent. It does not sandbox the
agent; file access is governed by the agent's own permission policy.

## The agent's environment

The agent inherits the bridge's environment with every variable whose name
starts with `ZULIP` removed, plus the file's `env`. That keeps Zulip
credentials out of the agent's environment. It does not keep them from the
agent: the agent runs as you and can read any file you can, including your
zuliprc files. Unless `zulip_tools = false`, the bridge passes the agent an
MCP server over ACP `mcpServers`: this package's server, run with the bot's
zuliprc. By default (`"ask"`) it runs with `--tool-profile ask-owner` and
offers one tool, `ask_owner`: the agent can reach you in its own conversation
and cannot read channels or message anyone else through it. With
`zulip_tools = true` the agent gets the server's whole tool set as the bot: it
reads every channel the bot can read and posts wherever the bot can post. Set
that only for a bot whose channels you would let steer the agent.

`ask_owner`:

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

From a terminal session of an agent that has a bot, run in the session's
workspace (in Claude Code or Clio, prefix it with `!`):

```bash
zulipchat-mcp-agents teleport clio            # or: teleport claude
zulipchat-mcp-agents teleport clio --session ID --cwd DIR --message TEXT
```

Without `--session`, the agent lists its sessions for `--cwd` (default: the
current directory) over ACP `session/list`, and the newest one is used: the
session you are in. The bot DMs you, and your reply resumes that session with
the bridge, which first tells the agent it is now reached through Zulip. Close
the terminal session first so two processes do not write the same session.

From an agent running elsewhere with this MCP server configured over stdio:

```text
teleport_chat(agent, message, session_id=None, cwd=None)
```

The agent bot named `agent` DMs its owner `message`. When the owner replies in
that DM, the bridge resumes `session_id` if given and supported, and otherwise
starts a fresh session in `cwd` (default: the file's `cwd`, which must lie in
`allowed_dirs`). The bridge must be running to answer. Errors are listed in
the [Agents API](../api-reference/agents.md#agent-bots).

## What you are trusting

An agent bot turns a Zulip account into a way to run a coding agent on your
machine. Decide with these facts:

- **The agent runs as you.** It has your files, your shell, your environment
  and your network, limited only by the agent's own permission policy.
  `allowed_dirs` chooses where it starts; it is not a sandbox. An agent set to
  approve its own actions (Clio `yolo`, Claude `bypassPermissions` or `auto`)
  never sends the permission requests described above.
- **Your Zulip login is a shell login.** Whoever can send messages as the
  bot's owner, or as a user in `allow`, drives the agent: a stolen session, a
  leaked API key, an unlocked phone. Every user ID in `allow` gets the same
  reach on your machine as you.
- **Text the agent reads can steer it.** Only admitted senders start turns,
  but with Zulip tools the agent can read channels, and a message written by
  any member, an integration or a web hook can carry instructions. Keep the
  bot out of channels whose authors you would not hand a terminal, and keep
  agents that read shared channels on a permission policy that asks.
- **Zulip sees everything the bridge posts.** Answers, questions, permission
  requests with their commands and paths, and the progress message with tool
  call titles all go to the conversation. The bridge replaces secret values it
  can recognize (credential-named environment values, the bot's API key,
  private keys, common token formats) with `[redacted]`. That is a net, not a
  guarantee.

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
