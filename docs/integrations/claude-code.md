# Claude Code

## Add the MCP server

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Dual identity

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

## Extended tool mode

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot \
  --extended-tools
```

## Export the richer Claude package

The old hook fragment is still available, but the preferred flow now is to scaffold a
real Claude package with hooks, project skills, and a session-operator subagent.

### Standalone `.claude/` assets

Export into a project root. This merges the Zulip hooks into `.claude/settings.json`
and writes the skill and subagent files alongside them.

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export \
  --client claude-code \
  --mode standalone \
  --output-dir . \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Installed assets:

- `.claude/settings.json`
- `.claude/skills/zulipchat-session-operator/SKILL.md`
- `.claude/skills/zulipchat-notifyme/SKILL.md`
- `.claude/skills/zulipchat-loop/SKILL.md`
- `.claude/agents/zulip-session-operator.md`

### Plugin package

Export a Claude plugin directory when you want a namespaced, shareable package.

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export \
  --client claude-code \
  --mode plugin \
  --output-dir ./zulipchat-plugin \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

That writes:

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `hooks/hooks.json`
- `skills/zulipchat-session-operator/SKILL.md`
- `skills/zulipchat-notifyme/SKILL.md`
- `skills/zulipchat-loop/SKILL.md`
- `agents/zulip-session-operator.md`

Load it locally with:

```bash
claude --plugin-dir ./zulipchat-plugin
```

## Claude hook bridge

For session lifecycle updates and in-topic approval waits, the package uses the
`zulipchat-mcp-hook` bridge:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-hook \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Typical Claude Code hook events for Zulip-controlled sessions are:

- `SessionStart`
- `PermissionRequest`
- `PostToolUseFailure`
- `Notification` for idle and waiting prompts
- `StopFailure`
- `TaskCompleted`
- `SessionEnd`

The hook bridge:

- registers a stable Claude agent profile
- binds the Claude session to a Zulip topic
- posts lifecycle updates into that topic
- waits for explicit `approve` / `deny` replies in-topic for permission requests
- exposes `ZULIPCHAT_AGENT_ID`, `ZULIPCHAT_SESSION_ID`, `ZULIPCHAT_SESSION_STREAM`,
  and `ZULIPCHAT_SESSION_TOPIC` to later shell commands in the same Claude session

## Included skills

### `/zulipchat-session-operator`

Use when you want the session to treat Zulip as its control plane. It instructs Claude
to poll `poll_agent_events`, obey `/status` `/pause` `/resume` `/cancel` `/handoff`,
and keep outbound traffic lifecycle-oriented.

### `/zulipchat-notifyme`

Use for deterministic manual posts into the bound Zulip topic:

```text
/zulipchat-notifyme blocked :: Waiting on production credentials
```

### `/zulipchat-loop`

Use when you want a continuous work loop that keeps reconciling with Zulip between work
cycles. If your Claude Code build exposes the native `/loop` command, use this skill as
the operating policy for each loop turn. If not, the same instructions still work in a
normal session.

## Included subagent

### `zulip-session-operator`

This subagent preloads the Zulip skills and is intended to own the communication and
owner-control plane while the main Claude thread focuses on implementation.

## One-command repo install

From this repository checkout:

```bash
./integrations/claude-code/install.sh
```

That script:

1. adds the `zulipchat` MCP server to Claude Code
2. exports the standalone `.claude/` assets into the current directory

## Legacy fragment

The minimal fragment is still available at:

- `integrations/claude-code/hooks.settings.fragment.json`

Use it only if you want to merge hooks manually and do not want the richer skill and
subagent packaging.

## Notes

- Claude Code supports `claude mcp add`, `claude mcp list`, and `claude mcp remove`.
- Use `--` before the MCP command.
- Template package: `integrations/claude-code/`.
