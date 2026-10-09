---
name: zulipchat-loop
description: Run the current Claude Code session as a continuous Zulip-aware work loop.
disable-model-invocation: true
---

# Zulip loop

Use this skill when you want the session to behave like a continuous autonomous worker
that still remains steerable from Zulip.

Treat `$ARGUMENTS` as the current mission or loop objective.

## Required setup

1. Read `ZULIPCHAT_SESSION_ID`, `ZULIPCHAT_SESSION_STREAM`, and
   `ZULIPCHAT_SESSION_TOPIC` from the shell.
2. If the session is not bound yet, stop and explain the missing hook setup.

## Loop contract

Each cycle should do exactly this:

1. Poll `poll_agent_events(session_id=..., limit=20)`.
2. Incorporate any owner steering or commands before doing more work.
3. Decide whether the lifecycle state changed. If it did, emit one lifecycle message.
4. Do one concrete unit of work toward the mission.
5. If blocked on owner input, call `request_user_input(...)` and wait.
6. Exit the loop when the mission is complete, the owner pauses or cancels the
   session, or the session binding is closed.

## `/loop` integration

If the current Claude Code build exposes the native `/loop` command, this skill's
instructions are the policy for each loop turn. If `/loop` is not available, follow
the same cycle in the current conversation instead of failing.

## Replies and reliable delivery

Questions use `/reply REQUEST_ID YOUR ANSWER`; approvals use `/approve REQUEST_ID`
or `/deny REQUEST_ID`. Call `wait_for_response(request_id=..., timeout_seconds=30)`
and retain the same request ID after a timeout. Do not post duplicate prompts.

Poll steering with `auto_ack=False` in the bound session. Handle each event, then
acknowledge its ID with `ack_event_ids` in the same session scope. Replayed events
must not repeat completed external actions. A delivered partial result includes
its message ID and `retry_safe=False`; inspect that result before retrying.
