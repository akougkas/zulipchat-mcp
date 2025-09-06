# Execution Prompt for AI Coder (YOLO mode)

Role
- You are a senior Python engineer and MCP specialist. Implement the refactor below end‑to‑end with high reliability, keeping MCP stdio-only. Make small, atomic commits per task. Do not leave TODOs unverified.

Operating constraints
- Transport: MCP stdio only (no HTTP server). Capabilities announced via FastMCP handshake.
- State: Persist all MCP state in DuckDB at `.mcp/zulipchat/zulipchat.duckdb`.
- Dependencies via uv. Use black/ruff/mypy before each commit. Avoid long‑running external processes.
- Tools are low-level MCP actions. Commands are human-facing workflows installed into client agents (not MCP tools).

Objectives (must all pass)
- Restructure codebase to the target layout (core/utils/services/tools/integrations) with correct imports.
- Implement mandatory DuckDB persistence (schema, migrations, DatabaseManager) and wire tools to it.
- Keep `server.py` thin: only tool registration + run.
- Provide integration installers + CLI for agent commands (Claude Code, Gemini CLI, OpenCode) that call MCP tools.
- Documentation aligned with Zulip REST, FastMCP, MCP concepts, and workflows.

Task plan with acceptance checks
1) Create packages and scaffolding
   - Create directories: `src/zulipchat_mcp/{core,utils,services,tools,integrations}` and subpackages with `__init__.py`.
   - Acceptance: Packages importable (`uv run python -c "import zulipchat_mcp; print('ok')"`).

2) Implement DuckDB DatabaseManager (utils/database.py)
   - Add `duckdb` dependency. Create DB at `.mcp/zulipchat/zulipchat.duckdb` (override `ZULIPCHAT_DB_PATH`).
   - Implement: connection, `threading.RLock` for writes, `execute/executemany/query`, `run_migrations` with schema from this plan.
   - Acceptance: One-liner smoke test creates DB and tables; queries return expected empty sets.

3) Move modules and fix imports
   - `client.py → core/client.py`; keep `core/{security,exceptions,cache,agent_tracker}.py`.
   - `commands.py → core/commands/engine.py` and extract `core/commands/workflows.py`.
   - `scheduler.py → services/scheduler.py`.
   - Update all imports in `tools/*` and elsewhere to `..core.*` and `..utils.*`.
   - Acceptance: `uv run mypy src/zulipchat_mcp` runs; no import errors (type issues can remain for later tasks).

4) Server wiring (FastMCP)
   - Ensure `server.py` registers only `tools/{messaging,streams,agents,search}` and calls `mcp.run()`.
   - Logging via `utils.logging`; no domain logic in server.
   - Acceptance: `uv run zulipchat-mcp` starts (stdio), lists tools in handshake (visible in client logs).

5) Tool registrars (low-level MCP API)
   - messaging: `send_message`, `edit_message`, `add_reaction`, `get_messages`.
   - streams: `get_streams`, `rename_stream`, `create_stream`, `archive_stream`.
   - search: `search_messages`, `get_daily_summary`.
   - agents: `register_agent`, `agent_message`, `wait_for_response` (blocking poll), `send_agent_status`, `request_user_input`, `start_task`, `update_task_progress`, `complete_task`, `list_instances`.
   - Validation using `core/security.py`; logging/metrics via `utils/*`; persistence via DatabaseManager.
   - Acceptance: Each tool returns structured responses and handles Zulip/API errors; DB rows created/updated per action.

6) Wire DatabaseManager usage
   - `core/agent_tracker` + `tools/agents` use: `agents`, `agent_instances`, `user_input_requests`, `tasks`, and `afk_state`.
   - Implement `wait_for_response` polling `user_input_requests` every ~1s until status is terminal.
   - Acceptance: Manual calls insert/select expected rows (e.g., register_agent creates agent + instance; request_user_input adds request; wait returns when response exists).

7) Integrations and CLI
   - `integrations/registry.py` with `main()` to route `zulipchat-mcp-integrate <agent> [--scope user|project] [--dir PATH]`.
   - `integrations/<agent>/installer.py` generates client-native command files for workflows (daily_summary, morning_briefing, catch_up) that call MCP tools.
   - `integrations/<agent>/capabilities.py` exposes optional agent-specific toggles.
   - Acceptance: Running CLI produces files in expected locations; commands match tool names and parameter schemas.

8) Documentation alignment
   - Update docs: clarify Tools vs Commands; remove examples/ references; add integration CLI usage.
   - Reference Zulip REST endpoints used; note auth env (`ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`).
   - Acceptance: Docs reflect final API and structure.

9) Sanity and cleanup
   - Run black/ruff/mypy on src; fix straightforward issues.
   - After green lints/types, remove deprecated wrappers/examples.
   - Acceptance: Clean tree; imports correct; server starts.

Integration map (must hold after each task)
- tools/* → core/* (domain logic) → utils/database (state) and core/client (Zulip REST) → external Zulip.
- agents tools ↔ DatabaseManager tables: afk_state, agents, agent_instances, user_input_requests, tasks.
- commands (client-side via installers) → MCP tools; no reverse dependency.

PRD Scenarios (E2E expectations)
- Agent registration + message
  1. Call `register_agent(agent_type="claude-code")` ⇒ DB: new `agents` row (if not exists), `agent_instances` row.
  2. Call `agent_message(content, require_response=False)` ⇒ Zulip message sent; success payload with message_id; DB unchanged.

- Human input request + wait
  1. Call `request_user_input(agent_id, question, context, options)` ⇒ DB: `user_input_requests` row (status="pending").
  2. Call `wait_for_response(request_id)` ⇒ blocks; when `status` becomes `answered`, returns `response`.

- Daily summary workflow (via client command)
  1. Client command triggers `search.get_daily_summary(streams?, hours_back)`.
  2. Tool fetches from Zulip and returns summary; may cache payload in `streams_cache`.

Close‑the‑loop conditions
- All tasks 1–9 completed with acceptance criteria satisfied.
- `uv run zulipchat-mcp` starts; handshake lists tools; basic tool calls succeed against Zulip (with valid creds).
- DuckDB created with required tables; DB state mutates correctly through tools.
- Integration CLI installs commands for at least one agent (Claude Code) and they call the correct tools.
- Docs reflect actual behavior and paths.

# Refactor Plan (ask user for changes in the direction of this plan if necessary)

### Core principles reflected
- MCP-first, stdio-only. Health is exposed via stdio and file-based status artifacts; all MCP state persists in DuckDB (https://duckdb.org/docs/stable/clients/python/overview.html).
- Tools are the low-level MCP API; “Commands” are human-facing workflows installed into client agents, not MCP tools.
- Adapter logic is implemented natively in the server under `integrations/` (inside src), no external hooks/scripts.
- Command-chain engine stays (slim, documented), used by client-side commands to call server tools.
- Keep code simple, composable, and transparent per agent patterns guidance [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

### Target layout (final)
- src/zulipchat_mcp/
  - server.py  (stdio entry; registers tool groups only)
  - core/      (domain and primitives)
    - client.py
    - agent_tracker.py
    - exceptions.py
    - security.py
    - cache.py
    - commands/         (engine + common workflows; NOT MCP tools)
      - engine.py
      - workflows.py     (prompt chaining, routing, etc. inspired by the article)
  - utils/     (cross-cutting)
    - logging.py
    - metrics.py
    - health.py
    - database.py             (DuckDB-backed persistence for state/cache/session/metrics)
  - services/  (long-lived/background)
    - scheduler.py
  - tools/     (MCP tool registrars only; no domain logic) $NOTE:{use your context7mcp tools for this to fetch the proper REST API for intergating with ZulipChat found in "https://zulip.com/api/rest"}
    - messaging.py
    - streams.py
    - agents.py
    - search.py
  - integrations/  (first-class agent integrations; no branding in core)
    - claude_code/
      - installer.py    (installs human-facing slash commands, hooks, and status line indicator for Claude Code) -> will be designed in another session
      - capabilities.py (declares optional agent-specific features)
    - gemini_cli/ -> will be enhanced in a later time
      - installer.py
      - capabilities.py
    - opencode/ -> will be only skeleton but implemented later
      - installer.py
      - capabilities.py
    - registry.py       (factory: resolve agent -> installer/capabilities)

Notes:
- Commands are distributed into client agents by the installers (not exposed as MCP tools).
- Tool registrars remain minimal; call into core/services only.
- No root-level examples/hooks/adapters. Any previous “bridge” logic becomes installer/capabilities within integrations/.

Alignment with README vision:
- Human ↔ AI collaboration is driven by a clear, documented MCP toolset (server side) and higher-level Commands (client side).
- Provide friendly default workflows (daily summary, morning briefing, catch up) via integrations’ installers that generate client-native command files.
- Keep async/caching transparent; prefer correctness and simplicity; persist state in DuckDB for reliability.

### Move and mapping plan (no behavior change initially)
- Move `client.py` → `core/client.py`.
- Keep `core/security.py`, `core/exceptions.py`, `core/cache.py`, `core/agent_tracker.py`.
- Move `commands.py` → `core/commands/engine.py`; extract `core/commands/workflows.py` (prompt chaining, routing, orchestrator-workers, evaluator-optimizer per the article).
- Keep `utils/logging.py`, `utils/metrics.py`, `utils/health.py`; add `utils/database.py` (DuckDB mandatory). (Drop prior `utils/fs.py` idea.)
- Move `scheduler.py` → `services/scheduler.py`.
- Keep `tools/*` as registrars; update imports to `core/*` and `utils/*` only.
- Remove `tools/commands.py` from server registration (commands are not MCP tools).

### API surface (MCP tools only)
- messaging: `send_message`, `edit_message`, `add_reaction`, `get_messages` (aligns with README)
- streams: `get_streams`, `rename_stream`, `create_stream`, `archive_stream`
- users: surface via `search` group as `get_users` (or a thin `org` subtool if needed later)
- search: `search_messages`, `get_daily_summary`
- agents: `register_agent`, `agent_message`, `wait_for_response`, `send_agent_status`, `request_user_input`, `start_task`, `update_task_progress`, `complete_task`, `list_instances` (implement thin, call into core/services)
- Explicitly: No “commands” as MCP tools.

Tool behavior rules
- Tools perform validation, call `core/*` and `services/*`, and return structured, minimal payloads.
- Logging/metrics via `utils/*`; sensitive data sanitized by `core/security.py`.
- Long-running loops are avoided inside tools; orchestrations belong to client-side commands using the engine. Exception: `wait_for_response` is intentionally blocking (per design) and polls DuckDB with a small sleep (e.g., 1s) until a response row is present.

### Integrations model (inside src)
- Each agent has an `installer.py` that:
  - Generates human-facing command files that call MCP tools in pre-defined workflows (using `core/commands/engine.py` semantics).
  - Is invoked by a neutral CLI entrypoint (e.g., `zulipchat-mcp-integrate <agent> [--scope user|project] [--dir PATH]`).
- Each agent has `capabilities.py` that tailors workflows (e.g., AFK-aware notifications, status indicators) without leaking brand specifics into core.
- `integrations/registry.py` maps agent ids/names → installer, capabilities, and exposes a simple Python API for programmatic installation.

### DuckDB integration (mandatory)
- Dependency: `duckdb` (install via uv/uvx; see https://duckdb.org/docs/installation). Python API ref: https://duckdb.org/docs/stable/clients/python/overview.html, docs index: https://duckdb.org/docs/index
- Database file: `.mcp/zulipchat/zulipchat.duckdb` (create directories/files if missing on startup).
- Connection lifecycle:
  - Single process-level connection: `conn = duckdb.connect(db_path)` created during server startup.
  - Reads can be concurrent; writes are serialized using an internal `threading.RLock` in `DatabaseManager`.
  - Wrap multi-statement writes in explicit transactions: `BEGIN; …; COMMIT;` (use `conn.execute` batching).
  - Close connection on graceful shutdown.
- Migrations:
  - Table: `schema_migrations(version INTEGER PRIMARY KEY, applied_at TIMESTAMP)`.
  - On startup: run idempotent `CREATE TABLE IF NOT EXISTS` for all required tables; record current schema version in `schema_migrations` if not present.
  - Versioned migration files/functions under `utils/database.py` (simple integer versions: 1, 2, …).
- Minimum schema (DDL):
  - AFK state
    ```sql
    CREATE TABLE IF NOT EXISTS afk_state (
      id INTEGER PRIMARY KEY,
      is_afk BOOLEAN NOT NULL,
      reason TEXT,
      auto_return_at TIMESTAMP,
      updated_at TIMESTAMP NOT NULL
    );
    ```
  - Agents and instances
    ```sql
    CREATE TABLE IF NOT EXISTS agents (
      agent_id TEXT PRIMARY KEY,
      agent_type TEXT NOT NULL,
      created_at TIMESTAMP NOT NULL,
      metadata TEXT
    );
    CREATE TABLE IF NOT EXISTS agent_instances (
      instance_id TEXT PRIMARY KEY,
      agent_id TEXT NOT NULL,
      session_id TEXT,
      project_dir TEXT,
      host TEXT,
      started_at TIMESTAMP NOT NULL,
      FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
    );
    ```
  - Human input requests
    ```sql
    CREATE TABLE IF NOT EXISTS user_input_requests (
      request_id TEXT PRIMARY KEY,
      agent_id TEXT NOT NULL,
      question TEXT NOT NULL,
      context TEXT,
      options TEXT,
      status TEXT NOT NULL,
      created_at TIMESTAMP NOT NULL,
      responded_at TIMESTAMP,
      response TEXT
    );
    ```
  - Task lifecycle
    ```sql
    CREATE TABLE IF NOT EXISTS tasks (
      task_id TEXT PRIMARY KEY,
      agent_id TEXT NOT NULL,
      name TEXT NOT NULL,
      description TEXT,
      status TEXT NOT NULL,
      progress INTEGER,
      started_at TIMESTAMP NOT NULL,
      completed_at TIMESTAMP,
      outputs TEXT,
      metrics TEXT
    );
    ```
  - Optional lightweight caches (do not gate correctness):
    ```sql
    CREATE TABLE IF NOT EXISTS streams_cache (
      key TEXT PRIMARY KEY,
      payload TEXT NOT NULL,
      fetched_at TIMESTAMP NOT NULL
    );
    CREATE TABLE IF NOT EXISTS users_cache (
      key TEXT PRIMARY KEY,
      payload TEXT NOT NULL,
      fetched_at TIMESTAMP NOT NULL
    );
    ```
- DatabaseManager (`utils/database.py`):
  - `init(db_path: str) -> None` (create path, connect, run migrations).
  - `run_migrations() -> None` (idempotent creation + version recording).
  - `execute(sql: str, params: tuple | list | None = None) -> None` (single write; lock + transaction wrapping when appropriate).
  - `executemany(sql: str, seq_params: list[tuple]) -> None` (batched writes; locked).
  - `query(sql: str, params: tuple | list | None = None) -> list[tuple]` (reads; no write lock).
  - Uses `?` parameter placeholders; converts Python types safely.
- Usage mapping:
  - `core/agent_tracker`: insert/select `agents`, `agent_instances`; manage AFK via `afk_state` (single-row convention with id=1).
  - `tools/agents`: `register_agent`, `agent_message`, `wait_for_response`, `request_user_input`, `send_agent_status`, `start_task`, `update_task_progress`, `complete_task`, `list_instances` operate through DatabaseManager.
  - `tools/search`/`tools/streams`: may optionally cache payloads in `*_cache` with TTL policy layered in code (not enforced by schema).

DatabaseManager skeleton (illustrative)
```python
import duckdb, os, threading, time
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = duckdb.connect(db_path)
        self._write_lock = threading.RLock()
        self.run_migrations()

    def run_migrations(self) -> None:
        self.conn.execute("""
          CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP
          );
        """)
        # v1 schema (idempotent)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS afk_state(
          id INTEGER PRIMARY KEY,
          is_afk BOOLEAN NOT NULL,
          reason TEXT,
          auto_return_at TIMESTAMP,
          updated_at TIMESTAMP NOT NULL
        );""")
        # ... (other CREATE TABLE statements from the plan) ...

    def execute(self, sql: str, params: tuple | list | None = None) -> None:
        with self._write_lock:
            self.conn.execute("BEGIN")
            try:
                self.conn.execute(sql, params or [])
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def executemany(self, sql: str, seq_params: list[tuple]) -> None:
        with self._write_lock:
            self.conn.execute("BEGIN")
            try:
                for p in seq_params:
                    self.conn.execute(sql, p)
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def query(self, sql: str, params: tuple | list | None = None) -> list[tuple]:
        cur = self.conn.execute(sql, params or [])
        return cur.fetchall()
```

Environment/config
- Default DB path: `.mcp/zulipchat/zulipchat.duckdb`.
- Override with env `ZULIPCHAT_DB_PATH` if set.
- Ensure directory creation is atomic and cross-platform.

Cache TTL policy
- `streams_cache`: TTL 600 seconds; `users_cache`: TTL 900 seconds (enforced in code before serving from cache; DB stores `fetched_at`).

Wait-for-response specifics
- `tools/agents.wait_for_response(request_id)` polls `user_input_requests` for `status IN ('answered','cancelled')`; returns `response` on success.
- Poll interval ~1s; include minimal logging and `send_agent_status` updates if appropriate.

### Documentation updates (high-level)
- Clarify “Tools vs Commands”: tools = MCP API; commands = human-facing workflows installed into client agents; commands call tools.
- Replace example-based instructions with `integrations/<agent>/installer.py` usage and the `zulipchat-mcp-integrate` CLI.
- Update `docs/commands.md` to reflect the new integration CLI and to remove any `examples/` references.
- Add a brief “Workflows” section describing prompt chaining, routing, orchestrator-workers, and evaluator-optimizer patterns, citing [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).
- Document stdio-only operation, file-based health artifacts, and mandatory DuckDB persistence (database path/env override, migration model, concurrency notes, and supported tables).
- Note FastMCP usage: follow current API; advertise capabilities in handshake; avoid unsupported constructor args (e.g., set description via capabilities/docs if not accepted).

Integration CLI spec
- Entry: `zulipchat-mcp-integrate <agent> [--scope user|project] [--dir PATH]`
- Agents: `claude_code`, `gemini_cli`, `opencode`.
- Exit codes: `0` success; `1` invalid args; `2` installation error.
- Behavior: generates client-native command files implementing workflows (daily_summary, morning_briefing, catch_up) that invoke MCP tools.

### FastMCP compliance and server wiring
- Framework: FastMCP (Python) — see `/jlowin/fastmcp` reference.
- Server entry (`src/zulipchat_mcp/server.py`):
  - Initialize server with stdio transport (default in FastMCP when run as console entrypoint).
  - Register tool groups only; no business logic in server.
  - Example skeleton:
    ```python
    from mcp.server.fastmcp import FastMCP
    from .tools import messaging, streams, agents, search
    from .utils.logging import setup_structured_logging, get_logger

    setup_structured_logging()
    logger = get_logger(__name__)

    mcp = FastMCP("ZulipChat MCP")
    messaging.register_messaging_tools(mcp)
    streams.register_stream_tools(mcp)
    agents.register_agent_tools(mcp)
    search.register_search_tools(mcp)

    if __name__ == "__main__":
        mcp.run()
    ```
- Tool registration: use `mcp.tool(description=...)` decorator/wrapper inside each registrar file to attach functions with clear docstrings and typed signatures.
- Capability announcement: rely on FastMCP’s handshake; ensure tool names, descriptions, and parameter schemas are accurate.
- No HTTP server; stdio only (per MVP).

### UV packaging and CLI
- Package management: `uv`.
- pyproject.toml:
  - Dependencies: `duckdb`, `zulip` (python-zulip-api), `pydantic`, `fastmcp` (pinned), `structlog` (optional), `typing-extensions` (if needed).
  - Console scripts:
    - `zulipchat-mcp = zulipchat_mcp.server:__main__` (or `:main` wrapper)
    - `zulipchat-mcp-integrate = zulipchat_mcp.integrations.registry:main`
- Commands:
  - Install deps: `uv sync`
  - Run server (stdio): `uvx --from git+<repo-url> zulipchat-mcp`
  - Integrate agent: `uv run zulipchat-mcp-integrate claude_code --scope user`

### Zulip REST integration specifics
- Client: use official Python bindings `zulip.Client` (see REST reference: https://zulip.com/api/rest).
- Authentication: Basic auth via API key; read from env `ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`.
- Endpoint mapping via client methods:
  - Send message → `client.send_message({type, to, content, topic?})` (REST: Send a message)
  - Edit message → `client.update_message({message_id, content? , topic?})` (REST: Edit a message)
  - Add reaction → `client.add_reaction({message_id, emoji_name})` (REST: Add an emoji reaction)
  - Get messages → `client.get_messages({anchor, num_before, num_after, narrow})` (REST: Get messages)
  - Get streams/channels → `client.get_streams(include_subscribed=True)` (REST: Get channels)
  - Get topics in a stream → `client.get_stream_topics(stream_id)` (REST: Get topics in a channel)
  - Get users → `client.get_users()` (REST: Get users)
- Narrow construction: use REST “Construct a narrow”; wrapper builds `[{"operator":"stream","operand":name}, ...]`.
- Error handling: inspect `result` field; on non-success, return structured error with `msg`; handle HTTP/network exceptions; consider brief retry/backoff on 429.
- Naming note: Zulip UI/docs may refer to “channels” (formerly streams). Keep consistent server-side naming but map via bindings.

### MCP protocol compliance
- Tools reflect low-level actions, with explicit parameter schemas and docstrings; names are stable and descriptive.
- No “commands” as tools; commands are installed into client agents via integration CLI and call these tools.
- Avoid side effects in tools beyond intended Zulip actions and DB updates; return compact JSON payloads.
- Provide clear errors and avoid ambiguous statuses.

### Step-by-step commits (atomic)
1) Create directories: `core/`, `utils/`, `services/`, `integrations/` scaffolds (no behavior change).
2) Move modules into new locations; update imports; keep server running; do not remove old files yet.
3) Extract `core/commands/engine.py` and `workflows.py`; ensure no commands are registered as tools; keep parity with README workflows (daily_summary, morning_briefing, catch_up) via engine.
4) Introduce `integrations/registry.py` and stub installers for `claude_code/`, `gemini_cli/`, `opencode/`; add CLI entrypoint `zulipchat-mcp-integrate`.
5) Update `server.py` to only register `messaging`, `streams`, `agents`, `search`; ensure capability advertisement matches MCP handshake.
6) Add dependency `duckdb`; implement `utils/database.py` (DatabaseManager); create `.mcp/zulipchat/zulipchat.duckdb` on startup; run migrations; verify required tables exist.
7) Update docs: tools vs commands, integration CLI, remove `examples/` references.
8) Sanity: black/ruff/mypy on src only (no tests yet).
9) Final cleanup: remove deprecated paths (old wrappers/examples) once structure is green.

### Risks/notes
- Removing `tools/commands.py` from server is necessary to honor “commands are NOT tools.”
- DuckDB concurrency: single-writer semantics – serialize writes with a process-level lock; avoid long transactions; keep writes small and frequent.
- Installers must not leak brand specifics into core; they transform client UX into standardized tool calls.
- Maintain file size budgets (~200–300 lines; split near 500–600 only when justified).

### Acceptance checklist
- Stdio-only; no HTTP surfaces. Health/metrics via stdio + DuckDB-backed state (database created at `.mcp/zulipchat/zulipchat.duckdb`).
- Migrations applied: `schema_migrations` present; required tables exist (`afk_state`, `agents`, `agent_instances`, `user_input_requests`, `tasks`; caches optional).
- `server.py` only registers tool groups and announces capabilities.
- Tools match README coverage; commands delivered via integration installers.
- No root-level examples/hooks/adapters. Integrations live under `src/zulipchat_mcp/integrations/`.
- Clear docs for Tools vs Commands, integration CLI, workflows, and DuckDB setup.
