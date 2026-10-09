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
- `poll_agent_events(limit=50, agent_id=None, session_id=None, event_type=None, auto_ack=True, ack_event_ids=None, include_audit=False)`

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
  timeout. Persisted terminal answers remain readable while Zulip is unavailable.
- Polling excludes outbound/unauthorized records by default. Set `auto_ack=False`
  for replay; pass consumed IDs through `ack_event_ids`, scoped by the session
  and/or agent supplied to that poll. `include_audit=True` exposes audit history.
- A delivered-but-unrecorded send returns `partial`, its message ID, and
  `retry_safe=False`; inspect the existing message before retrying.
- Lifecycle automation for Claude Code is intended to run through `zulipchat-mcp-hook`, not through AFK-style gating.
