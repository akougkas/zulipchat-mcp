"""Tools that connect a running agent to its Zulip agent bot.

teleport_chat hands the current conversation to an agent bot served by
`zulipchat-mcp-agents run`; the owner continues it in a direct message with the
bot. ask_owner exists only inside an agent the bridge launched: it asks the
owner in that agent's own Zulip conversation and waits for the answer.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from ..agents.config import config_dir, load_agent
from ..agents.store import BridgeStore
from ..agents.teleport import TeleportError, teleport
from ..config import get_client
from ..core.errors import api_error, tool_error
from ..core.security import local_access_allowed


def _refuse(error: str, code: str, **recovery: Any) -> dict[str, Any]:
    return tool_error(error, code, **recovery)


async def teleport_chat(
    agent: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            pattern=r"^[A-Za-z0-9_.-]+$",
            description="Agent bot name: a file name under "
            "~/.config/zulipchat-mcp/agents/ without .toml.",
        ),
    ],
    message: Annotated[
        str,
        Field(
            min_length=1,
            max_length=10000,
            description="What the bot DMs the owner: where the work stands.",
        ),
    ],
    session_id: Annotated[
        str | None,
        Field(
            max_length=200,
            description="This agent's own session ID, so the bridge resumes this "
            "exact session.",
        ),
    ] = None,
    cwd: Annotated[
        str | None,
        Field(
            max_length=4096,
            description="Working directory for a fresh session; defaults to the "
            "agent file's cwd.",
        ),
    ] = None,
) -> dict[str, Any]:
    """Hand this conversation to the owner's Zulip agent bot named `agent`.

    The bot DMs the owner `message` (summarize where things stand). The owner's
    replies there reach that agent through the local bridge. Pass the agent's
    own session_id to resume this exact session when the agent supports it;
    otherwise the bridge starts a fresh session in cwd.
    """
    if not local_access_allowed():
        return _refuse("teleport_chat works over stdio only", "POLICY_DENIED")
    if not message.strip():
        return _refuse("message cannot be empty", "BAD_REQUEST")
    path = config_dir() / f"{agent}.toml"
    if not path.is_file():
        known = sorted(p.stem for p in config_dir().glob("*.toml"))
        return _refuse(
            f"No agent bot '{agent}'; configured: {known}",
            "UNKNOWN_AGENT",
            hint="Pass one of the configured names, or create one with "
            "zulipchat-mcp-agents add.",
        )
    try:
        config = load_agent(path)
    except ValueError as error:
        return _refuse(str(error), "BAD_AGENT_CONFIG")
    workspace = Path(cwd).expanduser().resolve() if cwd else config.cwd
    try:
        response = await asyncio.to_thread(
            teleport, config, workspace, session_id, message
        )
    except TeleportError as error:
        return _refuse(str(error), error.code)
    if response.get("result") != "success":
        return api_error(response, "Handoff failed")
    result: dict[str, Any] = {
        "status": "success",
        "agent": agent,
        "message_id": response.get("id"),
        "resumes_session": session_id,
        "note": "The owner continues in a DM with the bot; the local bridge "
        "(zulipchat-mcp-agents run) must be running to answer.",
    }
    if response.get("message_link"):
        result["message_link"] = response["message_link"]
    return result


async def ask_owner(
    question: Annotated[
        str,
        Field(
            max_length=10000,
            description="The question; required unless question_id is given.",
        ),
    ] = "",
    question_id: Annotated[
        str | None,
        Field(
            max_length=100,
            description="ID of a question already asked, to keep waiting for its "
            "answer instead of asking again.",
        ),
    ] = None,
    wait_seconds: Annotated[
        int,
        Field(
            ge=0,
            le=840,
            description="Seconds to wait for the answer before returning pending "
            "(0-840).",
        ),
    ] = 300,
) -> dict[str, Any]:
    """Ask the owner a question in this Zulip conversation and wait for the answer.

    On timeout the question stays open: call again with question_id to keep
    waiting rather than asking twice.
    """
    state = os.getenv("ZULIPCHAT_AGENT_STATE")
    key = os.getenv("ZULIPCHAT_AGENT_CONVERSATION")
    if not state or not key:
        return _refuse("ask_owner only works inside a bridged agent", "NOT_BRIDGED")
    if not 0 <= wait_seconds <= 840:
        return _refuse("wait_seconds must be 0..840", "BAD_REQUEST")
    store = BridgeStore(Path(state))
    if question_id is None:
        if not question.strip():
            return _refuse("question cannot be empty", "BAD_REQUEST")
        bound = store.conversation(key)
        if not bound:
            return _refuse("This conversation is not bound", "NOT_BRIDGED")
        minutes = float(os.getenv("ZULIPCHAT_AGENT_QUESTION_MINUTES", "30"))
        question_id = store.ask(key, "question", question, [], minutes)
        where = bound["destination"]
        response = await asyncio.to_thread(
            get_client().send_message,
            where["type"],
            where["to"],
            f"**Question `{question_id}`**: {question}",
            where.get("topic"),
        )
        if response.get("result") != "success":
            return api_error(response, "Could not post the question")
    deadline = time.monotonic() + wait_seconds
    while True:
        row = store.question(question_id)
        if row is None or row["key"] != key:
            return _refuse(f"Unknown question {question_id}", "NOT_FOUND")
        if row["answer"] is not None:
            return {
                "status": "success",
                "question_id": question_id,
                "answer": row["answer"],
            }
        if time.time() > row["deadline"]:
            return {"status": "expired", "question_id": question_id}
        if time.monotonic() >= deadline:
            return {"status": "pending", "question_id": question_id}
        await asyncio.sleep(2)
