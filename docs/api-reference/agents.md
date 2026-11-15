# Agents API

Two tools connect an agent to its owner in Zulip. Both work with the local
bridge described in [Agent bots](../integrations/agent-bots.md): the owner talks
to a coding agent by messaging that agent's own Zulip bot. The MCP server cannot
wake an agent; the bridge (`zulipchat-mcp-agents`) is the only process that
listens to Zulip and starts agents.

The topic-bound session tools of 0.7 (`register_agent`, `ensure_agent_session`,
`agent_message`, `request_user_input`, `wait_for_response`,
`poll_agent_events`, `list_sessions`, `close_agent_session`) and the Claude hook
bridge were removed in 0.8.0.

## Agent bots

- `teleport_chat(agent, message, session_id=None, cwd=None)` (core)
- `ask_owner(question="", question_id=None, wait_seconds=300)` (core, bridged
  agents only)

`teleport_chat` hands the current conversation to the owner's agent bot named
`agent`, declared in `~/.config/zulipchat-mcp/agents/<agent>.toml`. The bot
sends `message` to its owner as a direct message; summarize where things stand.
The owner's replies in that DM reach the agent through the bridge
(`zulipchat-mcp-agents run`), which must be running to answer. With
`session_id`, the bridge resumes that ACP session when the agent supports
resuming or loading sessions; otherwise it starts a fresh session in `cwd`
(default: the agent file's `cwd`). `cwd` must lie inside the file's
`allowed_dirs`. The tool works over stdio only.

Errors: `POLICY_DENIED` (HTTP transport, or `cwd` outside `allowed_dirs`),
`BAD_REQUEST` (empty message), `UNKNOWN_AGENT` (lists the configured names),
`BAD_AGENT_CONFIG`, `BOT_UNREADABLE`, `OWNER_UNKNOWN` (the bot has no owner in
Zulip). Success returns `agent`, `message_id`, `resumes_session` and
`message_link` when Zulip provides one.

```python
teleport_chat(
    agent="clio",
    message="Tests pass; the migration still needs review. Continue here?",
    session_id="sess-1234",
)
```

`ask_owner` is registered only when `ZULIPCHAT_AGENT_STATE` is set, which the
bridge does for the Zulip server it injects into each agent (none is injected
when the agent file sets `zulip_tools = false`). It posts
`**Question `ID`**: ...` in that agent's Zulip conversation and waits up to
`wait_seconds` (0 to 840) for the owner's next message there, which becomes the
answer. Results:

- `status="success"` with `question_id` and `answer`.
- `status="pending"` with `question_id` when `wait_seconds` elapses. Call again
  with that `question_id` to keep waiting instead of asking twice.
- `status="expired"` once the agent file's `question_minutes` pass unanswered.
- `NOT_BRIDGED` outside a bridged agent, `NOT_FOUND` for an unknown ID.
