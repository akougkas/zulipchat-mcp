# Agent bots

Your coding agents get Zulip accounts. You DM "Claude" or "Clio" from your
phone; the agent runs on your machine, in your repositories, under its own
permission rules, and asks you in the chat when it needs a decision. Each agent
has its own Zulip Generic bot, called an agent bot. A local bridge,
`zulipchat-mcp-agents`, relays the conversation to the agent over the
[Agent Client Protocol](https://agentclientprotocol.com) (ACP). Nothing listens
on a port: the bridge connects out to Zulip.

The bridge is a separate long-running process, not part of the MCP server. An
MCP server lives as long as the host session that started it and cannot wake
an agent; the bridge holds the bots' event queues all the time and starts
agents when a message arrives. Both ship in the `zulipchat-mcp` package and
meet at two points: the bridge gives each agent this MCP server for
`ask_owner`, and the MCP server's `teleport_chat` hands a session to the
bridge.

Status: new in v0.8.0, which is not yet released. The bridge is tested with a
fake ACP agent and a mocked Zulip client, and in live use with Clio Coder.
Real Claude Code (`claude-agent-acp`) turns were run through it with a mocked
Zulip. OpenCode and Goose were probed for start, session creation and resume.

## Quick start

```bash
uv tool install zulipchat-mcp          # a background service needs a durable install
zulipchat-mcp-agents add claude        # creates the bot "Claude" with ~/.zuliprc
zulipchat-mcp-agents service install   # runs the bridge now and at every login
```

Then open Zulip on any device and DM the new bot. `~/.zuliprc` is your own
zuliprc (Zulip: Settings > Account & privacy > API key > Download zuliprc).

## How it works

- **One bot per agent.** An agent bot is declared in
  `~/.config/zulipchat-mcp/agents/<name>.toml`, which names the bot's zuliprc
  and the command that starts the agent in ACP mode.
- **No inbound ports.** For each bot, the bridge holds the bot's Zulip event
  queue over outbound HTTPS. By default it receives direct messages to the bot
  and @-mentions of the bot in every channel the bot can read; `listen`
  narrows that to direct messages or one channel. On first start it begins
  from the newest message; older messages are never replayed as work.
- **A durable queue.** Every message in scope lands in the bot's queue on disk
  before anything acts on it. The bridge drains the queue in order: messages
  from anyone not admitted are deleted, answers and commands are handled at
  once, and prompts wait under their conversation until its agent is free.
  A prompt leaves the queue only when its turn ends, so a message waiting
  behind a busy turn survives a restart. One process serves a bot: a second
  `run` while the service is up exits with status 78.
- **One conversation, one session.** A DM with the bot (keyed by its
  participants) or one channel topic is one ACP session, and it lasts until you
  send `/new`: idle stops, restarts and reboots resume it. The agent compacts
  its own context as the session grows. A session keeps the model the agent
  chose when it started, so after changing the agent's model settings, send
  `/new` to pick them up. Use separate channel topics for parallel threads. In
  a topic, a message must mention the bot to start a turn.
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
  yourself, stop the service (`systemctl --user stop zulipchat-mcp-agents` on
  Linux), start once with `zulipchat-mcp-agents run --accept-owner`, then
  start the service again.
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
  message that is only `yes`, `ok`, `okay` or `approve`, or only `no` or
  `deny`, in any case and with or without a final period (or `/approve ID`,
  `/deny ID`). Reactions answer nothing: they carry no client name, so an
  agent acting as you could approve itself with one. Any other message leaves
  it open. No answer within `question_minutes` means no. A request the agent
  withdraws, or that a `/cancel` ends, is closed in the conversation, so the
  next message starts a turn again. Clio withdraws main-session and worker
  requests alike when it gives one up.
- **Answers in a topic.** In a channel topic every message for the bot
  mentions it. The exception is an exact choice for the open request: `yes` or
  `no` for a permission, an option's number or label for an interview. A
  free-text answer needs the mention, and anything else you write there is
  ignored, so a remark to a colleague is never taken as your answer. A direct
  message needs no mention.
- **Clio Coder interviews.** The bridge tells Clio a person is attending
  (`clio-coder/interviews` and `clio-coder/workerPermissions` in
  `clientCapabilities._meta`). Clio's `ask_user` questions then arrive as
  `Question ID`, one at a time; reply with an option's number or label (several,
  comma-separated, when it allows more than one) or in your own words. The
  option Clio would take if nobody answered is marked `(recommended)`. Workers'
  permission requests arrive like any other permission request.
- **Restarts.** After a crash or restart the bridge tells each conversation
  whose turn was cut off that the earlier message may be only partly done; it
  never replays it. Prompts that were still waiting run then, unless they are
  more than 12 hours old: those get a reply saying they were not acted on.
  Requests the previous process asked are closed, so your next message is
  never taken as their answer.

## Lifecycle

| Piece | Starts | Stops |
| --- | --- | --- |
| MCP server | With each host session (Claude Code, Clio, …) | With that session |
| Bridge | At login, from `service install`; or `run` in a terminal | `service uninstall`, SIGTERM |
| Agent process | On a conversation's first message | After `idle_minutes` idle, `/new`, or with the bridge |
| Agent session | `session/new` on first use | Kept by the agent on disk and resumed on the next message, until `/new` |

- **Sleep and network loss.** The bridge backs off and retries. Zulip drops an
  idle event queue after about ten minutes; the bridge registers a new one and
  fetches what it missed from its saved cursor, so messages sent meanwhile are
  handled on wake.
- **Start without network.** The bridge waits, retrying from 5 seconds up to
  5 minutes, instead of exiting.
- **Reboot.** The service starts at login, or at boot with
  `loginctl enable-linger $USER` on Linux. Messages sent while the machine was
  off are handled then.
- **Crash.** systemd and launchd restart the bridge after 10 to 30 seconds.
  Errors a restart cannot fix (a refused zuliprc, an account that is not a bot,
  a changed owner, an invalid agent file) exit with status 78, which the
  systemd unit does not restart; `service status` shows the reason.

Per-bot state lives in `~/.local/state/zulipchat-mcp/agents/` (honoring
`XDG_STATE_HOME`): `<name>.sqlite3` holds conversation bindings and open
questions; `<name>-inbox.sqlite3` is the queue, holding only messages not yet
handled and prompts in flight. Rows are deleted as soon as they are handled,
and nothing stays past 30 days. An answer written
into the state file decides nothing: the bridge acts only on answers it took
from Zulip itself.

## Set up a bot

Create a Generic bot you own and declare it in one step. The owner zuliprc must
belong to a human, non-guest account; it defaults to `~/.zuliprc`:

```bash
zulipchat-mcp-agents add clio --cwd ~/projects
zulipchat-mcp-agents add claude --owner-zuliprc ~/.zuliprc-work
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

The adapter starts sessions in Claude's `auto` mode, which never asks. The
bridge switches each Claude session to `default` mode (ask before edits and
commands), so you approve from Zulip. Name another ACP mode in the file, for
example `mode = "acceptEdits"`, or `mode = ""` to keep Claude's own setting.

Clio Coder needs 0.8.2 or later. The bridge starts it as
`clio-coder acp --autonomy default`: a person in Zulip is not at the keyboard,
so Clio asks before it acts and refuses `yolo` for every session the bridge
hosts. To run it at your configured level, name the level in the file:
`command = ["clio-coder", "acp", "--autonomy", "yolo"]`. Read
[what you are trusting](#what-you-are-trusting) first.

The bridge tells Clio how long to wait for an answer (`timeoutMs` in both
opt-ins, equal to `question_minutes`), so a permission request or an interview
stays open in Clio as long as it stays open in Zulip. Do not add
`--permission-timeout` to the command: it overrides that window.

```bash
zulipchat-mcp-agents add reviewer \
  --command "my-agent --acp" --bot-zuliprc ~/.zuliprc-reviewer \
  --cwd ~/projects/app --allowed-dir ~/projects
```

Then validate and serve:

```bash
zulipchat-mcp-agents list
zulipchat-mcp-agents service install    # background, starts at login
zulipchat-mcp-agents service status     # state and recent log lines
zulipchat-mcp-agents service uninstall
zulipchat-mcp-agents run                # foreground instead (service stopped); --agent NAME, --debug
```

`list` exits non-zero if any file is invalid and notes commands missing from
`PATH`. `add` restarts an installed service, so a new bot is served at once;
after editing an agent file, run `service install` again to restart it.

`service install` writes a systemd user unit on Linux and WSL
(`~/.config/systemd/user/zulipchat-mcp-agents.service`; WSL needs systemd
enabled in `/etc/wsl.conf`) or a launchd agent on macOS
(`~/Library/LaunchAgents/io.github.akougkas.zulipchat-mcp-agents.plist`, logs
in `~/Library/Logs/zulipchat-mcp-agents.log`). Native Windows has no service;
keep `run` open. The service runs the interpreter that installed it, so install
with `uv tool install`; it refuses a temporary `uvx` environment. It records
your shell's `PATH`, which agents such as `clio-coder` and `claude-agent-acp`
(Node scripts) need. Other variables an agent needs, such as API keys set in a
shell profile, go in the agent file's `env`. Run `service install` again after
changing `PATH`.

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
mode = ""
listen = "all"
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
| `mode` | see below | ACP session mode set on every session; `""` keeps the agent's own. Unset: `default` for `claude-agent-acp`, the agent's own otherwise. A mode the agent does not offer fails the turn. |
| `listen` | `"all"` | What fills the queue. `"all"`: direct messages and @-mentions in every channel. `"dm"`: direct messages only. `"#channel"`: @-mentions in that one channel. Replies in a topic the bot is working in count without a mention in every scope. |
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
  `allowed_dirs` chooses where it starts; it is not a sandbox. The bridge holds
  Clio to `--autonomy default` and Claude to `default` mode. An agent file that
  lifts that (Clio `yolo`, Claude `bypassPermissions` or `auto`) means the
  agent never sends the permission requests described above.
- **The agent also loads its own configuration.** `zulip_tools` governs only the
  MCP server the bridge passes in. MCP servers in the agent's own user or
  project configuration load as well, with whatever identity they declare. The
  bridge ignores messages sent through this package's MCP server and never
  reads reactions, but an agent that holds your API key through another
  program can still post as you. Give agents the bot's identity, never yours.
- **Your Zulip login is a shell login.** Whoever can send messages as the
  bot's owner, or as a user in `allow`, drives the agent: a stolen session, a
  leaked API key, an unlocked phone, or the operator of a self-hosted Zulip
  server. Every user ID in `allow` gets the same reach on your machine as you.
  Organization administrators can read the bot's key and post as the bot, but
  the bridge never takes instructions from the bot's own messages.
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
- The bridge reads agent files at start. `add` restarts an installed service;
  after editing a file, run `service install` again.
- macOS launchd support is covered by unit tests only.
