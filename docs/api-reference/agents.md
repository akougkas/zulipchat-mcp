# Agents API

## Core tools

- `teleport_chat(to, message, wait_for_reply=False, reply_timeout=300, channel=None, topic=None)`
- `register_agent(agent_type="claude-code")`
- `agent_message(content, require_response=False, agent_type="claude-code")`
- `request_user_input(agent_id, question, options=None, context="")`
- `wait_for_response(request_id)`

## Extended tools

- `send_agent_status(agent_type, status, message="")`
- `manage_task(action, agent_id=None, task_id=None, name="", description="", progress=0, status="", outputs="", metrics="")`
- `list_instances()`
- `afk_mode(action, hours=8, reason="Away from computer")`
- `poll_agent_events(limit=50, topic_prefix="Agents/Chat/")`

## Examples

Register and send status:

```python
agent = await register_agent(agent_type="codex")
await send_agent_status(agent_type="codex", status="working", message="Analyzing stream")
```

Request input and wait:

```python
req = await request_user_input(
    agent_id=agent["agent_id"],
    question="Deploy now?",
    options=["yes", "no"],
)
await wait_for_response(req["request_id"])
```

## Behavior notes

- `agent_message` and `request_user_input` are AFK-gated by default.
- Set `ZULIP_DEV_NOTIFY=1` to bypass AFK gating in development.
- `teleport_chat` routes identity: bot for self-DM back-channel, user for org-facing messages.
