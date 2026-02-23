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
- Startup warms both caches in `server.py`.

## Security helpers (`core/security.py`)

- Stores unsafe-mode context flag.
- Provides validation/sanitization helpers.
- Includes optional rate-limiter primitives.

## Error handling (`core/error_handling.py`)

- Retry helpers and async rate-limiter primitives.
- Shared wrappers for robust tool-side calls where used.

## Services (`core/service_manager.py`, `services/`)

- Listener and AFK watcher behavior lives in service layer.
- Agent communication tooling uses persistent DuckDB-backed state.

## Tool registration (`tools/__init__.py`)

- `register_core_tools` defines the 19-tool baseline.
- `register_extended_tools` appends the extended tool set.
