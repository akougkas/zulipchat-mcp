---
name: zulipchat-session-operator
description: Run the current Claude Code session as a Zulip-controlled work session with topic-bound steering, approvals, and lifecycle updates.
disable-model-invocation: true
---

# Zulip session operator

Use this skill when the current Claude Code session is already bound to a Zulip topic
through `zulipchat-mcp-hook` and you want the rest of the work to respect that
control plane.

## Required setup

1. Read `ZULIPCHAT_SESSION_ID`, `ZULIPCHAT_SESSION_STREAM`, and
   `ZULIPCHAT_SESSION_TOPIC` from the shell before using any ZulipChat MCP tools.
2. If `ZULIPCHAT_SESSION_ID` is empty, stop and explain that the hook bridge has not
   initialized the session binding yet.

## Operating rules

1. Treat Zulip as the owner control plane for this session.
2. Poll `poll_agent_events(session_id=..., limit=20)` at the start of each work
   cycle, after each meaningful unit of work, and before going idle.
3. Interpret inbound events this way:
   - `steer`: treat the message as a high-priority owner instruction.
   - `command`: support `/status`, `/pause`, `/resume`, `/cancel`, and `/handoff`.
   - `approval_response`: only consume it when tied to a pending
     `request_user_input` approval flow.
4. Default notification policy is lifecycle-only. Use `agent_message` only for:
   `started`, `blocked`, `waiting`, `completed`, `failed`, or a targeted owner
   message that materially changes execution.
5. If you need a decision from the owner, call `request_user_input` instead of
   posting a freeform message.
6. Never spam the topic with token-by-token progress. One message per state
   transition is the expected behavior.
7. If you are running inside Claude's native loop mode, keep the same poll-work-post
   discipline for every loop turn.

## Command handling

- `/status`: send one concise status update covering current goal, next step, and any
  blockers.
- `/pause`: acknowledge, stop proactive work, and wait for a new owner message.
- `/resume`: acknowledge and continue from the current plan.
- `/cancel`: confirm the cancellation in the topic, stop work cleanly, and close the
  session if appropriate.
- `/handoff`: summarize state, remaining work, and risks for whoever takes over next.
- Any other slash command: reply once that it is not authorized or not supported by
  this session policy.

## Replies and reliable delivery

Questions use `/reply REQUEST_ID YOUR ANSWER`; approvals use `/approve REQUEST_ID`
or `/deny REQUEST_ID`. Call `wait_for_response(request_id=..., timeout_seconds=30)`
and retain the same request ID after a timeout. Do not post duplicate prompts.

Poll steering with `auto_ack=False` in the bound session. Handle each event, then
acknowledge its ID with `ack_event_ids` in the same session scope. Replayed events
must not repeat completed external actions. A delivered partial result includes
its message ID and `retry_safe=False`; inspect that result before retrying.
