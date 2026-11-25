# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current Status (v0.8.0, unreleased)

**PyPI has 0.7.6.** v0.8.0 lives on branch `release/v0.8.0` and is NOT released. The owner decides when to release; never tag, push, or publish without an explicit instruction. Check what is live with `curl -s https://pypi.org/pypi/zulipchat-mcp/json`.

Install from PyPI: `uvx zulipchat-mcp --zulip-config-file ~/.zuliprc`. Install this branch locally for dogfooding: `uv tool install --force --reinstall --from . zulipchat-mcp` (provides `zulipchat-mcp`, `zulipchat-mcp-agents`, `zulipchat-mcp-integrate`).

Companion commands use the same distribution: `uvx --from zulipchat-mcp zulipchat-mcp-integrate --help`. Always use `--from zulipchat-mcp` for the setup wizard, integration exporter, and agent bridge. The bridge's background service needs a durable install (`uv tool install`), not `uvx`.

### Production safety: grc-iit (grc.zulipchat.com)
The owner's real organization is production. Only the owner (Anthony Kougkas, user ID 502495, `~/.zuliprc-grc`) and his agent bot (user ID 1213477, `~/.zuliprc-grc-bot`, owner 502495) may be involved in any live test. Never message, mention, DM, react to, or create topics involving any other person; never post in shared channels for testing (prefer DMs between the owner and the bot). Never create or delete bots, change subscriptions, or edit other people's messages there without an explicit instruction. Read-only calls are fine. Use a mock Zulip (see `scripts/pancode_mcp_smoke.mjs`) for anything else.

### Where the work stands
- Done on the branch: dependency security bumps (FastMCP 4.1.4, authlib 1.9.1), Zulip API corrections by feature level, compact Markdown reads, `send_message` by name, removal of 13 redundant or LLM-calling tools and about 7,000 lines of dead code, and the agent bridge below.
- Architecture decision (2026-11-15, owner): the bridge is the only listener and the only way Zulip reaches an agent. The MCP-side control plane (register_agent … poll_agent_events, list_sessions, close_agent_session, the listener, `zulipchat-mcp-hook`, the session-operator/loop/notifyme skills, DuckDB) was deleted, about 9,500 lines. Its 0.7 flags (`--enable-listener`, `--associate-existing-db`, `--mention-allow`) are hidden no-ops that warn. Do not reintroduce a pull model in the MCP server.
- The agent bridge has unit and fake-agent tests, and real PanCode and Claude (`claude-agent-acp` 0.107.0) turns were driven through `AgentBridge` with a mocked Zulip client (prompt, resume, PanCode interview, progress). Live dogfooding on grc with the owner's agent bot is under way.
- Bridge lifecycle (installed as a login service on the owner's machine 2026-11-15, linger on; logs `journalctl --user -u zulipchat-mcp-agents`; reinstall the tool from the branch and `systemctl --user restart zulipchat-mcp-agents` to dogfood a change): `zulipchat-mcp-agents service install|uninstall|status` (`agents/service.py`) writes a systemd user unit or launchd agent that records the shell's PATH and runs `sys.executable -m zulipchat_mcp.agents.cli run`; it refuses a uvx environment. `add` defaults to `~/.zuliprc` and restarts an installed service. At start the bridge retries until Zulip is reachable; `BridgeConfigError` exits 78, which the unit does not restart. Claude sessions are set to ACP mode `default` (agent file `mode` overrides, `""` keeps Claude's own).
- Bridge features: PanCode HITL opt-in (`pancode/interviews`, `pancode/workerPermissions`, withdraw/cancel notifications), ACP `timeoutMs` from `question_minutes` in the opt-ins, one edited-in-place progress message per long turn, permission requests answered only by typed messages (reactions are ignored), `zulipchat-mcp-agents teleport NAME` resumes the newest local session for a cwd. Channels keep the mention-every-message rule (owner's decision).
- Declared on the owner's machine: an agent file under `~/.config/zulipchat-mcp/agents/` for his agent bot (cwd `~/projects`, allowed `~/projects` and `~/iowarp`); its command becomes `pancode acp`. The owner's user-level agent MCP config runs this branch's MCP server as `zulipchat-grc` with per-tool action classes (backup `mcp.yaml.bak-2026-11-15-zulipchat`). The agent runs at the owner's `yolo` autonomy in a terminal, but the bridge holds PanCode to `--autonomy default`.
- Security review done on the branch (2026-11-15): the working directory is no longer trusted (`.env` supplies only the five credential variables, no `./zuliprc` discovery, no `./.mcp/zulipchat` database), `listen_events` has no `callback_url`, and the bridge pairs with the bot's owner (`run --accept-owner` to pair again), redacts and silences what it posts, and gives agents only `ask_owner` unless the file says `zulip_tools = true` (new `--tool-profile ask-owner`). The owner's agent file now says `zulip_tools = "ask"`.
- Still open on the owner's machine, outside this repo: the agent's user-level `mcp.yaml` gives every agent session `zulipchat-grc` as the owner, now with `--tool-profile read-only` (2026-11-15, backup `mcp.yaml.bak-2026-11-15-readonly`), the agent runs `yolo` unsandboxed in a terminal, and his agent bot is subscribed to shared channels (one is web-public; Gnosis Github Metrics is fed by a GitHub integration). Text from those channels can still steer a bridged agent that runs shell as the owner. The owner decides those changes.
- No Claude Code agent bot exists on grc yet; the owner declined creating one for now. `claude-agent-acp` must be the global npm package (0.79.0 is too old for current models); `~/.local/bin/claude-agent-acp` points at the nvm v24.22.2 install.

## Project Overview

ZulipChat MCP Server v0.8.0 is a Model Context Protocol (MCP) server that enables AI assistants to interact with Zulip Chat workspaces. The project uses the FastMCP framework and an async-first architecture. The server keeps no conversation state; the agent bridge keeps its state in SQLite.

## Essential Development Commands

### Environment Setup
```bash
# Install dependencies. Never use pip; this project uses uv.
uv sync

# Run the MCP server locally
uv run zulipchat-mcp --zulip-config-file ~/.zuliprc

# Quick run via uvx
uvx zulipchat-mcp
```

### Testing & Quality Assurance
```bash
# Run tests (60% coverage gate)
uv run pytest -q

# Skip slow/integration tests for faster feedback
uv run pytest -q -m "not slow and not integration"

# Full coverage report
uv run pytest --cov=src

# Linting and formatting
uv run ruff check .
changed_py=$(git diff --name-only -- '*.py')
[ -z "$changed_py" ] || uv run black --check $changed_py
uv run mypy src

# Security checks (optional)
uv run bandit -q -r src
uv run pip-audit
```

### Development Testing
```bash
# Test connection to Zulip (uses installed package; safe inside or outside the repo)
uv run python -c "from zulipchat_mcp.config import ConfigManager; from zulipchat_mcp.core.client import ZulipClientWrapper; c = ZulipClientWrapper(ConfigManager()); print('Connected:', c.identity_name)"

# Import validation
uv run python -c "from zulipchat_mcp.server import main; print('OK')"
```

## Architecture Overview

### Core Structure
```
src/zulipchat_mcp/
├── core/           # Business logic (client, identity, commands, batch processing)
├── tools/          # MCP tool implementations (messaging, streams, search, events, users, files)
├── utils/          # Shared utilities (logging, redaction, metrics)
├── services/       # The bot message queue the bridge drains (bot_mentions.py)
├── agents/         # Local bridge: Zulip agent bots <-> ACP coding agents
├── integrations/   # AI client integrations
└── config.py       # Configuration management
```

### Key Components

- **Entry Point**: `src/zulipchat_mcp/server.py`, the MCP server with CLI argument parsing
- **Client Wrapper**: `src/zulipchat_mcp/core/client.py`, the dual identity Zulip API wrapper with caching
- **Tools**: `src/zulipchat_mcp/tools/*.py`, the MCP tool implementations
- **Configuration**: `src/zulipchat_mcp/config.py`, environment and CLI configuration
- **Account fingerprint**: `ConfigManager.resolved_account()` names the realm and
  principals; read caches live per fingerprint under `~/.local/state/zulipchat-mcp/accounts/`
- **Packaged skill**: one canonical `src/zulipchat_mcp/skills/zulipchat/SKILL.md`, a dependency-light
  loader, immutable Resources, and SEP-2640 discovery on MCP 2026-07-28
- **Integration exports**: native configurations for seven host families and
  schema-validated portable plugin content; host trust remains an operator action

### Dual Identity System
The client supports both user and bot credentials:
- User identity for reading/search operations
- Bot identity for posting messages and administrative tasks
- Identity switching via `switch_identity` tool

### Imports
Production code under `src/zulipchat_mcp/` uses package-relative imports:
```python
from .core.client import ZulipClientWrapper
from .tools.messaging import register_messaging_tools
```
Tests use `from src.zulipchat_mcp.*` because pytest runs with the repo root on `sys.path`. Never write `from src.zulipchat_mcp.*` inside `src/`.

## Tool Registration

Register tools through `tools/registration.py`, not bare `@mcp.tool`:
```python
from .registration import register_tool, optional_background_task

register_tool(
    mcp,
    my_tool_fn,
    name="my_tool",
    description="One-line, action-oriented.",
    task=optional_background_task(),  # only for long-running tools
)
```
Server-wide task advertisement is intentionally disabled in `server.py` (commit `70d3779`). Pass `task=optional_background_task()` only for genuinely long-running tools (e.g. `ask_owner`, `listen_events`). Normal fast tools omit `task=`.

## Tool Modes

- **Default**: 13 core tools (`CORE_TOOLS` in `tools/__init__.py`), registered via `register_core_tools(mcp)`. `ask_owner` is added only inside agents the bridge launches (`ZULIPCHAT_AGENT_STATE` set).
- **Extended (45 tools)**: enable with `--extended-tools` flag or `ZULIPCHAT_EXTENDED_TOOLS=1` env var. Calls `register_extended_tools(mcp)`.
- **Profiles** (`core/tool_contract.py`): `full`, `read-only` (`READ_ONLY_TOOLS`) and `ask-owner` (only `ask_owner`; what the bridge gives agents by default).

`tools/__init__.py` is the only place tools are registered. Each description leads with one self-contained sentence: PanCode's `gateway(op="find")` shows only that sentence.

## Development Guidelines

### Core Philosophy: Less is More
- **Elegant simplicity is the primary success metric**
- Achieve goals with minimal code - every line must justify its existence
- Prefer leveraging Zulip's native capabilities over custom implementations
- Remove complexity rather than managing it
- If a solution feels complicated, it probably is - find a simpler way

### Python Environment
- **Critical**: never use pip. Use `uv run` for all Python operations.
- Python 3.10+ required
- Use `uv add <package>` for dependencies, `uv sync` to synchronize

### Code Style
- Black formatting (line length 88)
- Ruff linting with pycodestyle, pyflakes, isort, bugbear, pyupgrade
- Type hints required for all public APIs
- Prefer async/await for I/O operations
- 4-space indentation, snake_case for functions/variables, CamelCase for classes
- **Minimize abstractions** - direct, clear code over clever patterns

### Testing Strategy
- Tests in `tests/` directory following pytest conventions
- Mark slow tests with `@pytest.mark.slow`, integration tests with `@pytest.mark.integration`
- Mock Zulip API calls to keep tests network-free
- 60% coverage gate enforced (`--cov-fail-under=60` in pyproject.toml)
- Use `uv run pytest` exclusively (no direct Python)

### File Operations
- **Always prefer editing existing files over creating new ones**
- **Consider deletion before addition** - can we solve this by removing code?
- Use Read tool before any file modifications
- Maintain existing code patterns and conventions

## Configuration

### Environment Variables
```bash
ZULIP_EMAIL=your@email.com
ZULIP_API_KEY=your_api_key
ZULIP_SITE=https://yourorg.zulipchat.com
ZULIP_BOT_EMAIL=bot@yourorg.zulipchat.com  # Optional
ZULIP_BOT_API_KEY=bot_api_key              # Optional
```

### CLI Integration
For Claude Code integration (tested syntax):
```bash
# From PyPI
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx zulipchat-mcp

# From GitHub (available now)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp

# From TestPyPI (for testing)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zulipchat-mcp
```

**Important**: Use the `--` separator to properly pass uvx arguments to Claude Code. Environment variables must come before the `--` separator.

## Security Notes
- Never commit credentials to repository
- Use `.env` file (gitignored) for local development
- Administrative tools are not exposed to AI clients
- All credentials handled via environment variables or CLI arguments

## Agent-Facing Behavior

### Agent bridge (`agents/`, command `zulipchat-mcp-agents`)
The MCP server is a tool surface; it cannot wake an agent. Inbound Zulip-to-agent traffic belongs to the bridge, a local process the owner runs (`zulipchat-mcp-agents service install` for a login service, or `run` in a terminal).
- One Zulip Generic bot per agent, declared in `~/.config/zulipchat-mcp/agents/<name>.toml` (`agents/config.py`). `zulipchat-mcp-agents add` writes it and can create the bot with the owner's key (`agents/provision.py`, `POST /bots`).
- The bridge holds the bot's event queue over outbound HTTPS only and drains a durable queue (`services/bot_mentions.py`, `<name>-inbox.sqlite3`): rows go `new` → `queued` (prompt, keyed by conversation) → `running` (one turn) → deleted. Strangers' rows, answers and commands are deleted on drain. At start, `running` rows get a "cut off mid-turn" notice and are never replayed, `queued` rows run unless older than `STALE_PROMPT_HOURS` (12), and open questions are closed. The bridge holds the inbox lease for its life, so a second process for the same bot exits 78. Agent file `listen` picks the scope: `all` (`ALL_SCOPE`), `dm`, or `#channel`. Owner = the bot's `bot_owner_id` in Zulip plus `allow` user IDs; everyone else is dropped without a reply.
- Each conversation (a DM with the bot, or a channel topic where the bot is mentioned) is one ACP session (`agents/bridge.py`), driven by the hand-rolled ACP client `agents/acp.py`. Agents start on the first message, stop after `idle_minutes`, and resume with `session/resume` or `session/load`. State lives in `~/.local/state/zulipchat-mcp/agents/<name>.sqlite3` (`agents/store.py`).
- Agents boot under their own permission policy. ACP `session/request_permission` is asked in the conversation; a bare `yes`/`ok`/`okay`/`approve` or `no`/`deny` (any case), or `/approve ID` / `/deny ID`, answers it, and silence means no. Reactions never answer: they carry no client name, so an agent acting as the owner could approve itself. PanCode interviews (`_pancode/interview/request`) are asked one question at a time. Long turns get one status message edited in place (`Progress` in `bridge.py`). `ask_owner` (in `tools/handoff.py`) uses the same questions table. `teleport_chat` binds a conversation to an agent bot so the owner continues in a DM.
- Bridge commands: `/status`, `/cancel`, `/new`, `/cwd PATH`, `/approve ID`, `/deny ID`. CLI `zulipchat-mcp-agents teleport NAME` (`agents/teleport.py`) shares its binding code with `teleport_chat`. The agent environment never carries `ZULIP*` variables; it gets this MCP server injected with the bot's zuliprc.
- Tests: `tests/agents/` (fake ACP agent `tests/agents/fake_acp_agent.py`).

### Token discipline
- Message rows come from `search.compact_message`: `id`, `from`, `time`, `text`, plus channel/topic only when not fixed by the query. Default `content_format` is Markdown and default `limit` is 20.
- `send_message` resolves names with `messaging._resolve_recipients`: exactly one match or nothing is sent.
- There is no server-side LLM. Clients summarize data themselves.

### Approved Emoji for Agent Reactions
Agents should use only these 12 emoji for consistency and quick responses:
- `thumbs_up`, `heart`, `rocket`, `fire`, `tada`, `check_mark`
- `warning`, `thinking`, `bulb`, `wrench`, `star`, `zap`

Invalid emoji (e.g., `thumbsup` without underscore) will fail at runtime. See `src/zulipchat_mcp/core/emoji_registry.py`.

## Common Issues

### Coverage / cache contamination
Clean environment before major test runs:
```bash
rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache
uv sync --reinstall
```

## Exported Claude assets

`zulipchat-mcp-integrate export --client claude-code` writes `.mcp.json` and
the portable `zulipchat` skill into `.claude/skills/` (standalone), or a Claude
plugin (`.claude-plugin/plugin.json`, `.mcp.json`, `skills/zulipchat/`). There
are no hooks: to reach a Claude session from Zulip, run it under an agent bot.

## Release Process

Full checklist and rationale in [RELEASING.md](RELEASING.md). Key invariants:

- Tag must match `pyproject.toml` version exactly (`v0.7.1` ↔ `version = "0.7.1"`).
- Version must be in sync across `pyproject.toml`, `src/zulipchat_mcp/__init__.py`, `src/zulipchat_mcp/tools/system.py`, `server.json`, and release docs. Run `uv run python scripts/release_preflight.py --version X.Y.Z` to verify.
- `scripts/pre_release_smoke.sh` is a blocking gate. It installs the built wheel and starts the MCP stdio server with fake credentials, catching startup-only failures that `--version` cannot.
- FastMCP feature changes require real-registration tests and the MCP stdio smoke. Pay special attention to optional extras, `task` support and async task functions.
- GitHub release must be published, not draft. `publish.yml` only triggers on `published`.
- After publishing, verify: GitHub release shows "Latest", PyPI shows new version, `uvx --refresh-package zulipchat-mcp zulipchat-mcp --version` installs it.

## Open Source & Community Practices

This is a public open-source project. Follow these practices when handling community interactions:

### Responding to Issues
- Acknowledge new issues within 48 hours, even if just "Looking into this."
- Apply labels on triage: `bug`, `enhancement`, `good first issue`, `help wanted`, `needs-triage`, `community`, `dependencies`, `fastmcp`, `mcp-tools`, `breaking-change`.
- When closing, explain what was fixed and which version contains the fix.
- Credit the reporter in release notes.

### Responding to Pull Requests
- **Respond within 48 hours.** Silence kills contributor motivation.
- Prefer merging community PRs over reimplementing the same fix independently. Contributors get credit in their GitHub contribution graph.
- If changes are needed, request them on the PR — don't close and reimplement.
- If a fix was already applied independently, close the PR with explicit credit and acknowledgment. Explain what happened.
- Label community PRs with `community`.

### Release Notifications
- After publishing a release, comment on all issues fixed in that release.
- Mention the version number, what was fixed, and how to upgrade.
- Invite reporters to try the new version and provide feedback.
