"""Agent bot declarations: one TOML file per Zulip bot that fronts a local agent.

    ~/.config/zulipchat-mcp/agents/clio.toml

    zuliprc = "~/.config/zulipchat-mcp/agents/clio.zuliprc"   # the bot's own key
    command = ["clio-coder", "acp"]                            # any ACP agent
    cwd = "~/projects"                                         # default workspace
    allowed_dirs = ["~/projects"]                              # /cwd may only pick these
    allow = []            # Zulip user IDs admitted besides the bot's owner
    idle_minutes = 30     # stop an idle agent process; its session resumes later
    question_minutes = 30 # unanswered permission requests and questions expire
    zulip_tools = true    # give the agent this server's Zulip tools, as the bot
    env = {}              # extra environment for the agent process

The bot's owner in Zulip is always admitted; nobody else is unless listed.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def config_dir() -> Path:
    base = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "zulipchat-mcp" / "agents"


def state_dir() -> Path:
    base = os.getenv("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "zulipchat-mcp" / "agents"


def _path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser().resolve()


@dataclass(frozen=True)
class AgentConfig:
    name: str
    zuliprc: Path
    command: list[str]
    cwd: Path
    allowed_dirs: list[Path]
    allow: frozenset[int] = frozenset()
    idle_minutes: float = 30
    question_minutes: float = 30
    zulip_tools: bool = True
    env: dict[str, str] = field(default_factory=dict)

    def permits_dir(self, path: Path) -> bool:
        return any(path == root or root in path.parents for root in self.allowed_dirs)

    def agent_env(self) -> dict[str, str]:
        """The agent's environment: never the owner's Zulip credentials."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("ZULIP")}
        return {**env, **self.env}

    @property
    def state_path(self) -> Path:
        return state_dir() / f"{self.name}.sqlite3"


def load_agent(path: Path) -> AgentConfig:
    """Parse and validate one agent file; raise ValueError with the reason."""
    name = path.stem
    if not _NAME.fullmatch(name):
        raise ValueError(f"{path.name}: agent names are lowercase, e.g. clio.toml")
    with path.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)
    unknown = set(raw) - {
        "zuliprc",
        "command",
        "cwd",
        "allowed_dirs",
        "allow",
        "idle_minutes",
        "question_minutes",
        "zulip_tools",
        "env",
    }
    if unknown:
        raise ValueError(f"{path.name}: unknown keys {sorted(unknown)}")
    command = raw.get("command")
    if not (
        isinstance(command, list)
        and command
        and all(isinstance(part, str) and part for part in command)
    ):
        raise ValueError(f"{path.name}: command must be a non-empty list of strings")
    if "zuliprc" not in raw:
        raise ValueError(f"{path.name}: zuliprc is required")
    cwd = _path(str(raw.get("cwd", "~")))
    allowed = [_path(str(item)) for item in raw.get("allowed_dirs", [str(cwd)])]
    allow = raw.get("allow", [])
    if not all(type(item) is int and item > 0 for item in allow):
        raise ValueError(f"{path.name}: allow takes numeric Zulip user IDs")
    env = raw.get("env", {})
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError(f"{path.name}: env values must be strings")
    config = AgentConfig(
        name=name,
        zuliprc=_path(str(raw["zuliprc"])),
        command=list(command),
        cwd=cwd,
        allowed_dirs=allowed,
        allow=frozenset(allow),
        idle_minutes=float(raw.get("idle_minutes", 30)),
        question_minutes=float(raw.get("question_minutes", 30)),
        zulip_tools=bool(raw.get("zulip_tools", True)),
        env=dict(env),
    )
    if not config.permits_dir(cwd):
        raise ValueError(f"{path.name}: cwd must be inside allowed_dirs")
    return config


def load_agents(directory: Path | None = None) -> list[AgentConfig]:
    directory = directory or config_dir()
    return [load_agent(path) for path in sorted(directory.glob("*.toml"))]
