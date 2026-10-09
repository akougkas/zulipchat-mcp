# Named organization profiles: proposed next feature

This design is not implemented in v0.7.4. It starts with selecting one named
organization at process startup and preserves current credentials when no profile
is selected. Runtime switching requires another design.

Store a versioned registry at `~/.config/zulipchat-mcp/profiles.json`. Each profile
names an absolute user zuliprc path, an optional bot zuliprc path, and a separate
data directory. Keep API keys in restrictive credential files, outside the
registry. Reject unknown fields, duplicate names, unreadable files, mismatched
user/bot sites, and ambiguous selection before constructing clients.

Proposed precedence is an explicit profile selection, then a profile environment
variable, then today's credential selection. A selected profile and explicit
credential-path overrides should be mutually exclusive: combining them risks
silently selecting a different organization. Preserve the existing rule that a
selected credential file supplies its email, key, and site as one unit.

Derive a stable organization identifier from the normalized site and profile
name. Scope client/cache keys, DuckDB paths, listener state, agent profiles,
sessions, and tasks to it. An operator should be able to run two separate stdio
processes without sharing persistent state. HTTP should continue serving one
configured organization per process; request arguments must not select another
organization or credential file.

Acceptance tests should use two fake organizations with deliberately identical
user IDs and stream names. Assert isolation of reads, writes, cache entries,
pending approvals, listener cursors, scheduled work, and restart persistence.
Also test malformed registries, missing credentials, selection conflicts, and
the unchanged no-profile credential contract. No live credentials are needed.

Implement in small steps: typed registry parsing and startup selection, isolated
storage construction, then CLI/docs/client templates. Do not add a runtime
switching tool in the first implementation. That tool must settle what happens
to live listeners, in-flight API calls, persisted requests, and host sessions.
