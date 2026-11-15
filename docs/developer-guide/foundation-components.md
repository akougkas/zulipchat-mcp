# Foundation Components

## Configuration (`config.py`)

- Reads only the five credential variables (`ZULIP_EMAIL`, `ZULIP_API_KEY`,
  `ZULIP_SITE`, `ZULIP_BOT_EMAIL`, `ZULIP_BOT_API_KEY`) from a `.env` in the
  current working directory, and only when the real environment sets none of
  that credential set.
- Supports `zuliprc` file path discovery and explicit paths.
- Maintains current identity (`user` or `bot`).
- Exposes `get_client()` and `get_bot_client()` wrappers.

## Client wrapper (`core/client.py`)

- Wraps Zulip Python client with convenience methods.
- Handles identity-specific credential selection.
- Provides cached `get_users()` and `get_streams()` paths.
- Includes helpers for message retrieval, stream/topic APIs, and file URL normalization.

## Caching (`core/cache.py`)

- User and stream caches are used for fast fuzzy resolution.
- Clients and their account-isolated caches initialize lazily. Startup does not
  query Zulip to warm caches.

## Security helpers (`core/security.py`)

- Stores the unsafe-mode context flag.
- Provides emoji and email validation helpers.

## Request shaping (`core/api_budget.py`, `core/api_errors.py`)

- `PoliteZulipClient` admits each request once per principal, spaces requests,
  honors Zulip rate-limit cooldowns, and never retries transparently.
- `api_error` turns a failed Zulip response into a tool error result.

## Persistent state (`core/snapshots.py`)

- The server keeps no account database. Bounded read snapshots live per
  account in SQLite files under
  `$XDG_STATE_HOME/zulipchat-mcp/accounts/<fingerprint>/cache`.
  `--ephemeral-state` keeps them in memory and writes no files.

## Agent bridge (`agents/`, `services/bot_mentions.py`)

- `zulipchat-mcp-agents` is the only process that listens to Zulip and wakes
  agents. It holds each agent bot's event queue and drives one ACP session per
  conversation. See [Agent bots](../integrations/agent-bots.md).

## Tool registration (`tools/__init__.py`)

- `register_core_tools` defines the 13-tool baseline (`ask_owner` is added
  inside agents the bridge launches).
- `register_extended_tools` appends the extended tool set.
