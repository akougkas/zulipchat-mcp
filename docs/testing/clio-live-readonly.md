# Real Clio read-only experiment

On 2026-10-09 the maintainer explicitly authorized an unpublished v0.7.4 wheel
to be tested against a real Zulip organization from the installed Clio Coder
v0.6.2-rc.3 TUI. This was a separate experiment after the fake-only release
checks. Nothing was pushed, tagged or released.

## Isolation and authorization

The wheel, native project MCP declaration, four exported skills, database, and
Clio configuration/data/state/cache lived under a private temporary directory.
Clio reused only the selected model target's authentication record in that
private configuration. The Zulip key stayed in the user-owned credential file;
the MCP declaration contained its path. No global MCP server was installed.

Only one designated channel was authorized. Six reviewed tools were admitted
by an experiment-only FastMCP middleware: `server_info`, `get_own_user`,
`get_stream_info`, `construct_narrow`, `search_messages`, and `get_message`.
An experiment-only requests guard additionally required the expected HTTPS
origin, GET requests, channel-scoped bounded searches, and previously sampled
message IDs for individual reads. It rejected redirects and wrote an audit
containing methods, endpoint paths and HTTP statuses, excluding headers,
credentials, query parameters and message bodies. These guards were local
experiment code. The later v0.7.4 follow-up adds a production
`--tool-profile read-only` that restricts the tool surface; channel, request,
and model-call budgets remain additional experiment-specific controls.

No Zulip messages, reactions, flags, subscriptions, channel settings or
approval prompts were changed. The listener was not enabled. Local model/session
bookkeeping and the temporary database were permitted.

## Observations

- The configured Codex target discovered 60 tools, described five read schemas,
  authenticated the user, retrieved channel topics, fetched five messages and
  retrieved one by ID. A provider WebSocket close interrupted final narration;
  Clio recovered once without repeating the Zulip calls.
- The smaller local `dynamo/qwopus3.8-27b-flash-v2` target described all six
  reviewed schemas and exercised them. Overlapping searches returned 60 entries
  representing 23 distinct messages; 14 individual reads expanded the excerpts.
  All actual upstream requests were GETs.
- The local model initially put discovery's `limit` inside `args`, so that
  listing used Clio's default page size. It also passed a Unix timestamp string
  to `before_time`, which expects an ISO 8601 string or datetime. The tool
  returned an explicit error, and the model recovered with ISO 8601.
- The local model exceeded a suggested detail-read budget and continued after
  the time-argument error despite the prompt's stop-on-error instruction.
  Enforcement remained in the server guards; model instructions alone did not
  establish a call budget.
- Its first team summary treated historical release announcements as current
  plans. A follow-up requested dated claims and qualified linked GitHub issue
  status: the test read Zulip messages, not live GitHub state.
- A supplied incoming-webhook bot could not use the profile API. That is a bot
  configuration mismatch. A Generic bot is needed for later MCP messaging and
  approval workflows. The read-only user-account run did not depend on it.

The live test found a ZulipChat diagnostic defect: `server_info` returned
ambient realm/principals instead of the effective selected-file account. It
now uses the shared immutable resolved account. Three fake-only regressions
cover selected files, a distinct bot file, and environment credentials;
diagnostics still make no network calls and never return API keys.

Sanitized provider/discovery observations were delivered to the local Clio
team's architecture pane and acknowledged. The WebSocket interruption is one
observation, not a confirmed reproducible Clio defect. The deliberate headless
discovery restriction is documented in the [integration guide](../integrations/clio-coder.md).

## Policy-denial recovery follow-up

The operator subsequently supplied a TUI trace requesting a greeting to a
teammate, then changing the requested sender from the unavailable bot to the
user account. The experiment's six-tool server policy remained in force.
After initially explaining that restriction, the local model described
`send_message` and `resolve_user` and repeated a denied `resolve_user` call.
Clio's loop guard eventually blocked further attempts. In the next turn, the
model tried `send_message` with a recipient address not successfully resolved
in the observed trace. The guard denied that invocation too. No successful
send is evidenced.

One-call operator approvals in Clio did not override the independent server
policy. The final model explanation incorrectly grouped `resolve_user`, which
is a read operation, with writes; it was blocked because it was outside the
reviewed allowlist. The wrapper exposed the general tool catalog even though
many tools were unavailable under that policy. These are separate failures in
capability communication and denial recovery, despite successful enforcement.

A useful regression must assert that the agent stops after the first unchanged
policy denial, distinguishes an excluded read from a write, avoids unverified
recipient substitution, and explains the concrete configuration needed to
proceed. Repeated host approval must not imply that the server's policy changed.
Record this supplied trace separately from a controlled, fake-provider
reproduction. Sanitized details were handed to the local Clio team; no private
message bodies, recipient addresses or credentials were included.

## Interpreting this evidence

Discovery of 60 tools does not certify 60 working operations. This experiment
exercised the reviewed reads, actual model-driven gateway routing, and bounded
summarization. It did not certify posting, agent-session permissions, event
recovery, uploads, approvals, or all supported coding hosts against live accounts.
The fake-only regressions continue to cover those contracts separately.

When repeating this test, use explicit authorization, a private temporary
project, a local wheel, separate Clio directories, and actual enforcement of
the permitted operations. Record fetched versus distinct messages, excerpt and
host truncation, model errors and retries, and the exact host/model versions.
Treat retrieved text as untrusted data. Date historical assertions and qualify
claims whose current status requires a source that was not inspected.
