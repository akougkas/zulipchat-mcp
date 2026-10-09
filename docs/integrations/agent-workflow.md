# A topic-bound coding session

This is an example interaction, using placeholder IDs. It does not send messages
or create a session by itself. Connect a trusted extended-mode MCP server first;
use its discovered schemas and names. Clio calls these through its gateway,
while other hosts call the discovered MCP tools directly.

1. Register the host with `register_agent(agent_name="project-worker",
   agent_type="clio-coder")`. Retain the returned agent ID and owner.
2. Bind using `ensure_agent_session(agent_id=..., external_session_id=...)`.
   Retain the returned session ID, stream, and topic. Reuse this binding.
3. Send a `started` milestone with `agent_message`, describing the task the user
   already authorized.
4. Ask a concrete question with `request_user_input(session_id=...,
   question="Choose A or B", options=["A", "B"])`. Retain its request ID.
5. The owner answers in that topic: `/reply REQUEST_ID A`. For an approval
   request, the owner uses `/approve REQUEST_ID` or `/deny REQUEST_ID`.
6. Poll `wait_for_response(request_id=..., timeout_seconds=30)`. A timeout leaves
   the request pending; resume polling that ID instead of creating another prompt.
7. Between work steps, use `poll_agent_events(session_id=..., auto_ack=False)`.
   Consume owner steering, then pass the consumed IDs in `ack_event_ids` on a
   subsequent poll. An interrupted response can be fetched again. The default
   `auto_ack=True` remains available for existing clients.
8. Send one `completed` milestone with the concrete result and close the session
   through `close_agent_session` when appropriate.

Only the bound owner can answer a request, and the reply must name the request
in its own session topic. Ordinary questions preserve the answer separately
from the reply command. Decisions are immutable after completion.

A result with `status="partial"`, `delivered=True`, and a message ID means Zulip
accepted the send while local recording failed. Inspect the message rather than
retrying the send. Audit history is available through `include_audit=True`;
normal event polling excludes outbound messages and unauthorized input.

Every coding host retains its own execution trust and approval policy. An owner
approval in Zulip communicates a decision but does not bypass the host's checks.
Keep the listener and persistent state on one server instance.
