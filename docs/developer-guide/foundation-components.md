# Foundation Components

## Configuration (`config.py`)

- Loads `.env` from current working directory when present.
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

- Stores unsafe-mode context flag.
- Provides validation/sanitization helpers.
- Includes optional rate-limiter primitives.

## Error handling (`core/error_handling.py`)

- Retry helpers and async rate-limiter primitives.
- Shared wrappers for robust tool-side calls where used.

## Services (`core/service_manager.py`, `services/`)

- Listener startup/supervision lives in the service layer.
- Inbound topic messages are classified into session events and owner-policy decisions.
- Agent communication tooling uses persistent DuckDB-backed state shared with the Claude hook bridge.

## Agent control plane (`core/agent_control.py`, `core/agent_protocol.py`)

- Stable agent profiles and topic bindings are coordinated outside the tool layer.
- Shared parsing helpers classify topic replies into steering, command, and approval events.
- Session lifecycle messages use a consistent topic format and owner-controlled request flow.

## Tool registration (`tools/__init__.py`)

- `register_core_tools` defines the 20-tool baseline.
- `register_extended_tools` appends the extended tool set.
