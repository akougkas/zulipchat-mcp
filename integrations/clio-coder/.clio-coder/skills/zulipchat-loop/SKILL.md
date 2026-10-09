---
name: zulipchat-loop
description: Reconcile an explicitly requested ongoing coding task with owner steering in its bound Zulip topic between work cycles.
license: MIT
---

Use this workflow only for the continuing task the user authorized. Retain the
current session binding, objective, constraints, event cursor, and outstanding
request IDs. Between substantial work cycles, poll `poll_agent_events`, process
verified owner commands, then continue useful task work and post meaningful
milestones through `agent_message`.

Stop when the task is complete or canceled. Pause only at the owner's request.
When input is required, persist the concrete request and wait without treating
elapsed time as a decision. A host-native scheduling or loop facility may drive
the cycles; this skill does not install one or grant additional permissions.

For owner questions, advertise `/reply REQUEST_ID YOUR ANSWER`. For approval
requests use `/approve REQUEST_ID` or `/deny REQUEST_ID`. Poll with
`wait_for_response(request_id=..., timeout_seconds=30)` and retain the same
request ID after a timeout. Resume polling instead of posting a duplicate prompt.
For replayable steering, use `poll_agent_events(auto_ack=False, session_id=...)`
and acknowledge consumed event IDs on the next poll with `ack_event_ids`.
