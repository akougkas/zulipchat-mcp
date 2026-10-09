# Agents API

The agent tool family is now session-oriented: bind an agent profile, bind a Zulip topic to a session, send lifecycle updates into that topic, and read owner commands back out.

## Core tools

- `teleport_chat(to, message, wait_for_reply=False, reply_timeout=300, channel=None, topic=None)`
- `register_agent(agent_name="claude", agent_type="claude-code", owner_email=None, stream_name=None, topic_prefix="Agents/Session", metadata=None)`
- `ensure_agent_session(agent_id, external_session_id=None, topic_name=None, project_dir=None, project_name=None, status="active", metadata=None)`
- `agent_message(session_id, content, category="message", request_id=None, metadata=None)`
- `request_user_input(session_id, question, options=None, context="", request_type="question", metadata=None)`
- `wait_for_response(request_id, timeout_seconds=300)`

## Extended tools

- `send_agent_status(agent_id, status, message="")`
- `manage_task(action, agent_id=None, task_id=None, name="", description="", progress=0, status="", outputs="", metrics="")`
- `list_sessions(agent_id=None, include_closed=True)`
- `list_instances()` — compatibility alias for session listing
- `close_agent_session(session_id, status="completed", summary="")`
- `poll_agent_events(limit=50, agent_id=None, session_id=None, event_type=None, auto_ack=True, ack_event_ids=None, include_audit=False, mentions_stream=None, after_message_id=None, wait_seconds=0, direct_messages=False)`

## Ordinary bot mentions

With a configured Generic bot, a host can read explicit mentions in a channel
without an existing session:

```python
batch = poll_agent_events(
    mentions_stream="Agents-Channel",
    after_message_id=previous_cursor,
    auto_ack=False,
    wait_seconds=20,
    limit=20,
)
```

This mode returns `events`, `bot_user_id`, `next_after_message_id`, listener
health and local-cache/recovery counters. Each event includes numeric sender,
channel and message IDs, topic, timestamp, raw content and truncation state.
`direct_messages=True` reads direct and group-direct messages to the bot instead,
with its own cursor; no mention is needed. Its events add `recipients` and
`reply_to`, every participant except the bot.

The server only returns events from senders admitted by `--mention-allow` or
`ZULIPCHAT_MENTION_ALLOW`: by default the configured owner alone, or the owner
plus listed emails and numeric user IDs, or `everyone`. Other senders appear in
`ignored_unauthorized` with IDs and no content, and the cursor still advances
past them. `authorization` and `server_info.mention_authorization` report the
policy. Check `status`, readiness and `cache.cursor_gap` before
dispatching. The host commits its cursor with a durable work queue and deduplicates
tasks by message ID. No event acknowledgement SQL is used in mention mode.

`limit` is 1–50; `wait_seconds` is 0–25 and waits on local state. Startup may
wait up to 20 seconds for readiness. Do not combine mention mode with session
filters, `ack_event_ids` or audit mode. At most four channels can be watched per
server. The background producer uses scoped long polling rather than fetching
history for every host poll. Edited/deleted inputs become tombstones, and a
consumer behind the 10,000-message retention limit receives an explicit gap.

Retain one stable agent/topic session for successive tasks and use `agent_message`
to reply in that topic. Normal mentions need no `/reply` syntax. The server
does not launch a coding process, grant native permissions or supervise it;
see [host ownership and efficiency](../developer-guide/zulip-api-proxy.md).

## Example flow

Register a stable Claude profile:

```python
agent = register_agent(agent_name="claude", agent_type="claude-code")
```

Bind the current Claude session to a Zulip topic:

```python
session = ensure_agent_session(
    agent_id=agent["agent_id"],
    external_session_id="claude-session-123",
    project_dir="/home/you/project",
)
```

Send a lifecycle update:

```python
agent_message(
    session_id=session["session_id"],
    content="Waiting on deployment approval.",
    category="waiting",
)
```

Ask for an approval and wait:

```python
req = request_user_input(
    session_id=session["session_id"],
    question="Approve running migrations in production?",
    options=["approve", "deny"],
    request_type="approval",
)
await wait_for_response(req["request_id"], timeout_seconds=30)
```

## Behavior notes

- Session topics are owner-controlled by default.
- Inbound topic replies are classified as `command`, `approval_response`,
  `question_response`, or `steer` events.
- Unauthorized users get a visible `Not authorized` reply in the topic.
- Questions require `/reply REQUEST_ID ANSWER`, preserve multiline answers, and
  cannot be used to approve a permission request. Approval replies must name the
  request with `/approve REQUEST_ID` or `/deny REQUEST_ID`.
- Use `timeout_seconds=30` for bounded waits, retaining the request ID after a
  `status="timeout"`, `request_status="pending"` result. Persisted terminal
  answers remain readable while Zulip is unavailable.
- Polling excludes outbound/unauthorized records by default. Set `auto_ack=False`
  for replay; pass consumed IDs through `ack_event_ids`, scoped by the session
  and/or agent supplied to that poll. `include_audit=True` exposes audit history.
- A delivered-but-unrecorded send returns `partial`, its message ID, and
  `retry_safe=False`; inspect the existing message before retrying.
- Lifecycle automation for Claude Code is intended to run through `zulipchat-mcp-hook`, not through AFK-style gating.
