# Live Clio bot mentions

On 2026-10-09, the maintainer authorized an isolated live experiment with a
Generic Zulip bot, the installed Clio Coder v0.6.2-rc.3 TUI, and the smaller
`gpt-6-luna` model. An additional visible Codex worker drove the experiment.
The dedicated Luna TUI ran beside the maintainer's pane. This followed the
[earlier read-only experiment](clio-live-readonly.md); its authorization and
measurements are separate.

## Observed workflow

Four ordinary owner mentions in the designated bot channel were ingested,
dispatched to the real Luna session and answered by the Generic bot in their
original topic. No `/reply` syntax was needed. Actual MCP results, the pinned
Clio transcript, a durable host ledger and an independent HTTP audit agreed on
one successful bot post for each source message. The first three requests were
short conversational greetings; the fourth requested a five-message catch-up.
This establishes bounded read/summarize behavior, not a computer-editing task.
Private evidence retains the source/result IDs and
timestamps without publishing the institution's message ledger.

The host adapter verified the numeric bot, channel and owner IDs, persisted
source-message deduplication, admitted one task at a time, and drove only the
specific native approval cards permitted by this experiment. Its agent MCP
allowed nine reviewed tools, with an independent HTTP guard limiting the
origin, bounded reads and one bot send in the verified source topic. Its
listener MCP allowed only diagnostics and mention polling. This selected
demo allowlist differs from the production `read-only` profile.

Zulip credentials stayed in private local credential files. The native MCP
declaration, installed local wheel, exported skills, account-bound database,
Clio provider configuration, state and caches were scoped to one temporary
project. Authentication headers, credentials and message bodies were excluded
from the HTTP audit. The experiment did not install a global MCP declaration
or edit the shared Clio checkout. The main TUI was not an OS sandbox; its prompt,
native admission and server guard were distinct controls.

## Failures found and corrected

The first Herdr prompt response arrived before the task appeared in the actual
transcript. The prototype correctly retained `needs_review` rather than
resending. Inspection established that the original task was running; its
completed result and wire post were then reconciled. The private adapter now
waits briefly for that same transcript append and never sends a second prompt
merely because delivery metadata is ambiguous.

The second source initially failed because the prototype created a new external
session ID for every mention. The MCP server correctly rejected a topic already
bound to a session. Both transcript and wire audit established that this attempt
made no send. The host then reused the verified existing binding and recovered
only that source, which posted once. Task IDs and stable topic-session IDs are
now separate. A subsequent third mention completed automatically with the same
binding and no recovery.

Herdr also reported an input-ready completed TUI as `done`, while the prototype
initially admitted only `idle`. The corrected gate accepts completed state only
with a persisted terminal outcome and no pending call. These were private
host-adapter integration defects; this experiment did not establish a new
shipped Clio defect. Sanitized observations are retained for the Clio team.

## Bounded API measurements

A private measurement snapshot at 16:31:45 UTC recorded the following totals
across initial startup and the local adapter corrections:

| Wire operation | Count |
| --- | ---: |
| Listener event GETs | 27 |
| Mention-history GETs | 2 |
| Event-queue registrations | 2 |
| Queue deregistrations | 1 |
| Bot message POSTs | 3 |
| Listener server-settings/profile GETs | 10 / 1 |
| Agent server-settings GETs | 2 |

The steady initial process fetched history once. Restarted host processes reused
the durable inbox and reported zero new history fetches. Event GETs were blocking
long polls, with heartbeat responses, rather than repeated message-history
queries. The aggregate two history requests include startup/recovery and must
not be presented as one total request. No other HTTP mutations appeared in the
audit. The three message POSTs each had a distinct verified owner source and
HTTP 200. These are counts at a particular time; event polling continues while
the live listener runs.

Fake tests provide the broader correctness evidence: repeated local inbox
polls need one history fetch and one outstanding event poll; replay overlaps
deduplicate; storage failure cannot advance the acknowledgement; changed/deleted
input becomes a tombstone; expired queues recover by message ID; competing local
producers fail before an API call; and restart re-verifies the numeric bot ID.
Separate wire tests cover cache/error metadata and the minimum/latest framework.

## Final-wheel read and summary

After final wheel alignment, an actual owner mention requested a catch-up on the
five most recent messages in the same topic, with UTC dates, message IDs and
explicit uncertainty. The visible Luna turn completed in about 21 seconds.
It made one `search_messages` call with the exact channel/topic, newest-first
ordering and `limit=5`. One upstream message-window GET fetched and returned
five untruncated messages. The model reused that result without a detail read
or repeated search, then made one successful source-topic bot post. The
independent audit records HTTP 200 for that read and post, plus three read-only
SDK server-settings requests during agent startup. Bootstrap requests are
counted separately from message retrieval.

The reply included all five IDs and correct UTC timestamps, described the
conversation, and qualified decisions/follow-ups against the limited sample.
The five newest messages included the request itself, as the prompt did not
exclude it. It did not infer the nature of unspecified work or claim a wider
team/project audit. The actual final MCP result, completed Luna transcript,
source/post budget and HTTP audit agreed; there was no extra acknowledgement
post, changed Zulip state beyond the requested reply, or replay. The host
persisted completion and continued serving ordinary owner mentions.

## Shipping boundary

The shipped MCP addition is the event-fed, account-scoped mention inbox exposed
through `poll_agent_events`. The visible Clio launcher/approval adapter remains
a private experiment, not a universal unattended runner installed by the
integration exporter. Clio owns model launch, native permissions, workspace
execution and settlement. ZulipChat MCP owns authenticated Zulip transport,
recovery, snapshots and persisted control events. See
[API coverage and efficiency](../developer-guide/zulip-api-proxy.md) for the
implementation contract and [the control design](../developer-guide/zulip-agent-control-design.md)
for future host supervision and cancellation work.

After the three greetings settled, the owned host and TUI processes were
quiesced and their exits verified. The final wheel was installed into the same
private environment; all 74 installed Python/skill files matched its bytes.
The visible Luna session was resumed, and one adapter restarted from the durable
cursor without replaying the completed sources. The new listener re-verified
the bot, held its kernel producer lease, recovered with one bounded history
read, and reported ready with no gap. A competing lease acquisition failed
without starting another producer. A final mapper correction was installed
after quiescing only the host/listener; the resumed TUI stayed visible. All
74 installed Python/skill files matched the final wheel. The listener reused
its persisted queue with zero new history reads and remained ready. The bounded
summary above then exercised that final artifact live.

The final release candidate is also checked with rebuilt-wheel, fake-credential
protocol and actual Clio-client smokes. These checks do not retroactively turn
the earlier greetings into certification of all final source changes.
No push, tag, GitHub release or package publication is part of this experiment.
