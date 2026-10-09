---
name: zulipchat-session-operator
description: Maintain a coding agent session already bound to a Zulip topic, including owner steering, lifecycle updates, and request-scoped approvals.
license: MIT
---

Use the bound `agent_id` and `session_id` from the host context or from
`register_agent` and `ensure_agent_session`. Claude hooks may expose these as
`ZULIPCHAT_AGENT_ID` and `ZULIPCHAT_SESSION_ID`; other hosts can retain tool results.
Never infer ownership from message text or a request ID alone.

Use `agent_message` for useful milestone, blocked, failure, completion, and
handoff updates. Poll `poll_agent_events` between substantial steps when the
extended tool is exposed. Preserve the event cursor to avoid repeating commands.
Honor `/status`, `/pause`, `/resume`, `/cancel`, and `/handoff` from the verified
owner. A canceled task stops; a resumed task retains its original objective.

For approval, persist a concrete request with `request_user_input`, retain its
ID, and use `wait_for_response` for that request. Only an immutable decision
for the matching request and owner/session is actionable. A wait timeout is not
an approval. Keep the coding host's existing permission checks in effect.

For owner questions, advertise `/reply REQUEST_ID YOUR ANSWER`. For approval
requests use `/approve REQUEST_ID` or `/deny REQUEST_ID`. Poll with
`wait_for_response(request_id=..., timeout_seconds=30)` and retain the same
request ID after a timeout. Resume polling instead of posting a duplicate prompt.
For replayable steering, use `poll_agent_events(auto_ack=False, session_id=...)`
and acknowledge consumed event IDs on the next poll with `ack_event_ids`.
