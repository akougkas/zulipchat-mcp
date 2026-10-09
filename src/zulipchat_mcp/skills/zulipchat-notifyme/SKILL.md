---
name: zulipchat-notifyme
description: Send a user-requested status or result update to the current Zulip-bound agent session.
license: MIT
---

Resolve the current session binding and send the requested update with
`agent_message`. Use the user's category when supplied, otherwise `message`.
Keep the content focused on the requested result, progress, or blocker. Include
relevant artifact links and verification evidence without credentials or unrelated
conversation history. Check the tool result and report delivery errors accurately.

For owner questions, advertise `/reply REQUEST_ID YOUR ANSWER`. For approval
requests use `/approve REQUEST_ID` or `/deny REQUEST_ID`. Poll with
`wait_for_response(request_id=..., timeout_seconds=30)` and retain the same
request ID after a timeout. Resume polling instead of posting a duplicate prompt.
For replayable steering, use `poll_agent_events(auto_ack=False, session_id=...)`
and acknowledge consumed event IDs on the next poll with `ack_event_ids`.
