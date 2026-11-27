# Zulip API coverage and efficient agent access

Reviewed on 2026-10-09 for v0.7.4. The review used Zulip's complete
[canonical OpenAPI](https://github.com/zulip/zulip/blob/main/zerver/openapi/zulip.yaml),
[real-time event documentation](https://zulip.com/api/real-time-events),
[HTTP headers and rate limits](https://zulip.com/api/http-headers), and the
installed Zulip SDK 0.9.1. The reviewed OpenAPI bytes have SHA-256
`d179f23dba27fb1f0f571998fea18ad1bc774c01dcf421a6dc1df7313ff10f28`.
Upstream documentation on `main` changes independently of this release.

ZulipChat MCP is a curated agent interface to Zulip. Its 13 core or 53 extended
tools cover messaging, search, channels/topics, people, drafts, scheduled
messages, reminders, attachments, reactions, flags, events and agent-bot
handoff. It does not expose unrestricted REST forwarding. Authentication-key
creation, organization administration, invitations, mobile push, and many
browser-specific operations remain outside the registered surface. Some
additional operations exist only as internal client wrappers.

The [operation inventory](zulip-api-coverage.json) records every method/path
entry in the reviewed OpenAPI, distinguishes registered tools from internal
wrappers and unexposed operations, and identifies three documentation-only
entries. It records static tool-to-client reachability for the 0.8.0 tool
surface. This is a coverage inventory, not a claim that every parameter,
permission, or operation was exercised against a live server. The tests
exercise representative registered-tool and upstream boundaries.

## Snapshot reads and event deltas

```mermaid
flowchart LR
    Agent[Agent MCP calls] --> Reads[Identity-scoped read snapshots]
    Reads --> Budget[Realm and principal request budget]
    Budget --> API[Zulip REST API]
    API --> Queue[Bot event queue]
    Queue --> Inbox[Durable local bot inbox]
    Bridge[zulipchat-mcp-agents] --> Inbox
    Bridge --> ACP[ACP agent session]
```

Message windows and individual message reads cache successful API responses
for 15 seconds. Each wrapper's scope includes its realm, principal and selected
user/bot identity. Raw Markdown and rendered HTML requests have different keys.
Identical concurrent reads in one process share a fetch. Each cache retains
at most 64 responses of at most 512 KiB each; larger responses are returned
without being cached. API errors are never stored as successful snapshots.

Server caches persist in the account's cache directory,
`$XDG_STATE_HOME/zulipchat-mcp/accounts/<fingerprint>/cache`, unless
`--ephemeral-state` keeps them in memory. A same-account restart can reuse a still-fresh response. Returned cache metadata includes the
capture time in UTC, age, TTL, content hash and hit/miss state. `fresh=True` on
`search_messages` or `get_message` bypasses reuse. Recovery paths always fetch
new upstream windows. Successful sends, edits, explicit-ID flag updates and
received message events invalidate same-process realm snapshots. Other changes,
including bulk flag/reaction operations, changes made by another process or in
unwatched channels, can remain cached until the short TTL expires; use
`fresh=True` to verify the immediate result of those operations. A cached
response during an API cooldown remains a dated observation, not a new one.

The agent bridge keeps a separate rolling inbox per agent bot in
`$XDG_STATE_HOME/zulipchat-mcp/agents/<name>-inbox.sqlite3`. It holds the
bot's direct and group-direct messages plus its @-mentions in every channel the
bot receives, and every message in the 50 most recent channel topics where the
bot holds a conversation, so the owner can answer there without a mention. The inbox registers its event queue before fetching history,
then persists new message events and the event cursor in one transaction. The
bridge reads this local inbox; it does not repeat the history query. The
producer uses blocking event polling, including heartbeat responses. Empty
fast responses have a minimum delay, and failures use bounded exponential
backoff and the server's retry delay.

One producer per inbox is enforced with an OS advisory lock held by its worker
for its lifetime. Another process for the same bot follows the owner's snapshot
and takes over if that process exits. The bridge advances a shared delivery
cursor with compare-and-set, so each message reaches one bridge process. On
first start the cursor begins at the newest message; old messages are never
replayed as work. These local locks do not provide distributed ownership across
machines.

On queue expiration, the producer registers a replacement before recovering
messages after its durable message-ID watermark, then deduplicates the overlap.
Recovery is bounded to 20 pages of 50 per registration attempt. Persistent
recovery progress survives a retry.

The inbox retains at most 10,000 messages for at most 30 days, with message
text capped at 6,000 characters. The bridge drops each message once it is
delivered or refused. Deleted and edited inputs become tombstones rather than
silently becoming a new task. Truncation and a consumer falling behind
retention are explicit (`content_truncated`, `cursor_gap`).

## Rate limits and truthful outcomes

Zulip documents a default limit of 200 requests per user per minute; deployments
can configure different limits. Client wrappers in one MCP process share
admission by normalized realm and principal. Requests are spaced at least
0.5 seconds apart, with a bounded two-second admission wait. Official
`X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers can
reduce the launch rate. These are request-start limits: an outstanding long
poll does not hold the admission lock.

HTTP 429, JSON `RATE_LIMIT_HIT`, JSON `retry-after`, numeric or HTTP-date
`Retry-After`, and reset headers impose a shared cooldown. A call during that
cooldown returns a retryable result with the remaining delay without making an
upstream request. The SDK's transparent retry loops are disabled, including
its special long-poll retry loop. The bridge's inbox producer makes its own
bounded recovery decisions. Writes are submitted once; callers must resolve uncertain
delivery before retrying. Budgets are per process, not a global quota shared
with other clients using the same account.

Tools preserve backend error codes and retry instructions where available.
Application `status="error"` becomes MCP `isError=true`, so hosts do not show
a failed operation as a successful call. A requested channel detail that fails
is `partial` with a component error, while available basic information remains
usable. A Zulip send followed by failed local recording retains its delivered
message ID and unsafe-retry warning. An `ask_owner` wait that ends before an
answer is `pending`, not a failure; call again with its `question_id`.

## REST semantics that agents must preserve

- Search returns a bounded window. Report fetched and returned counts, UTC
  dates, bounds, excerpt truncation and the cache observation time. An empty
  window is not proof that a channel has no older messages.
- Follow message-ID anchors for pagination and stop when the backend reports
  the relevant boundary. Recovery uses date anchors only at feature level 445
  or newer; older servers use message-ID pagination. Zulip timestamps have
  integer-second precision.
- Zulip sends accept Markdown. Copy operations fetch raw Markdown rather than
  forwarding rendered HTML. Ordinary search explicitly labels rendered
  excerpts; individual reads keep the compatibility default.
- HTTP cannot access the server's local upload paths. Arbitrary binary input
  uses bounded, strictly decoded `file_content_base64`; the existing text
  input remains available.
- Bulk flag operations paginate the actual registered tool. Starring includes
  already-read messages. A later-page failure reports partial progress.
- Selected credential files supply their realm and principal together. Bot
  environment credentials without a separate file use the selected user's
  effective realm. Read caches are bound to the effective account's
  fingerprint; a change of organization starts a new cache rather than
  migrating one.
- Zulip increasingly calls streams “channels”; stable numeric IDs are the
  host's routing authority, while older SDK field names remain compatible.
  `server_info`'s configured bot name is a label. The authenticated bot profile
  and numeric `bot_user_id` establish the actual identity.

The OpenAPI comparison corrected numeric stream lookup to `GET /streams/{id}`,
subscription-property fallback to `POST /users/me/subscriptions/properties`,
and topic-mute fallback to `PATCH /users/me/subscriptions/muted_topics`.
Fake tests assert the upstream method/path and both legacy and modern MCP
results. The reviewed endpoints retain Zulip's compatibility display behavior
for empty topics; this release does not claim a complete new-topic API migration.

## Efficient host workflow and ownership

The MCP server is a tool surface for an agent that is already running. It owns
Zulip credentials, API translation, read caches and message transport. It
cannot wake an agent. The separate `zulipchat-mcp-agents` bridge is the one
component that listens to Zulip and launches agents; see
[Agent bots](../integrations/agent-bots.md). PanCode, Claude or another ACP agent
owns model selection, workspace admission, native tool permissions and
cancellation. Installing an MCP declaration or skill does not start an
unattended runner. Treat message content as user task data, never as a tool
definition or executable shell command.

Start with a bounded search and reuse its result. Expand only the selected
message IDs whose omitted content matters. Stop unchanged policy-denial retries.
Keep the `question_id` of a pending `ask_owner` call instead of asking twice. Validate claims about
current GitHub or project state against those sources rather than interpreting
an old Zulip announcement as current status.

## Local privacy and operational limits

Snapshot and bridge inbox files contain Zulip message content. They use private file
permissions and reject symlink destinations; no API keys are stored in them.
TTL controls whether a read can be reused, not deletion of every expired byte.
Protect the account cache directory and the bridge state directory, include
both in local data-retention decisions, and clear the `cache` directory after
stopping the server when needed.
Do not publish live ledgers or institutional message bodies with test artifacts.

Bridge state and producer ownership remain single-machine local workflows.
Shared static HTTP authentication is not per-user authorization. A bot inbox
is not a computer-execution permission grant. Linux locks and source/package
contracts were tested; the Windows lock implementation was not.
