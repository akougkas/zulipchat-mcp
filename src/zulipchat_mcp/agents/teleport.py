"""Continue a local agent session in a direct message with its agent bot.

The conversation is bound to the session before the bot writes, so the
bridge resumes that session on the owner's next message. When no session ID
is given, the newest session the agent lists for the workspace is used: run
from a terminal session, that is the session the owner is in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from .acp import AcpAgent, AcpError
from .config import AgentConfig
from .provision import ProvisionError, bot_owner_id
from .store import BridgeStore


class TeleportError(Exception):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


async def latest_session(config: AgentConfig, workspace: Path) -> dict[str, Any]:
    """The agent's most recently updated session in ``workspace``."""
    agent = AcpAgent(config.command, env=config.agent_env(), cwd=str(workspace))
    try:
        await agent.start()
        sessions = await agent.list_sessions(str(workspace))
    except AcpError as error:
        raise TeleportError(
            f"{config.name} could not list sessions: {error}", "ACP"
        ) from error
    finally:
        await agent.close()
    here = [s for s in sessions if s.get("cwd") in (None, str(workspace))]
    if not here:
        raise TeleportError(f"{config.name} has no session in {workspace}", "NONE")
    return max(here, key=lambda s: str(s.get("updatedAt") or ""))


def teleport(
    config: AgentConfig, workspace: Path, session_id: str | None, message: str
) -> dict[str, Any]:
    """Bind the owner's DM with the bot to ``session_id`` and post ``message``."""
    if not config.permits_dir(workspace):
        raise TeleportError(
            f"{workspace} is not in {config.name}'s allowed_dirs", "POLICY_DENIED"
        )
    bot = ZulipClientWrapper(ConfigManager(config_file=str(config.zuliprc)))
    try:
        owner = bot_owner_id(bot)
    except ProvisionError as error:
        raise TeleportError(
            f"Cannot read agent bot '{config.name}': {error}", "BOT_UNREADABLE"
        ) from error
    if owner is None:
        raise TeleportError(
            f"Agent bot '{config.name}' has no owner in Zulip", "OWNER_UNKNOWN"
        )
    BridgeStore(config.state_path).bind(
        f"dm:{owner}",
        session_id,
        str(workspace),
        {"type": "private", "to": [owner]},
    )
    return bot.send_message("private", [owner], message)
