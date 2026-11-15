"""Bridge one Zulip agent bot to a local ACP agent.

The bot's event queue is the only inbound channel: no ports are opened and the
bridge reaches Zulip over outbound HTTPS. Every Zulip conversation with the bot
(a direct message, or one channel topic) is one ACP session. Agent processes
start on demand and stop when idle; their sessions resume on the next message.
Only the bot's owner and explicitly allowed user IDs are heard; anyone else is
dropped without a reply.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..services.bot_mentions import ALL_SCOPE, BotMentionInbox
from ..utils.logging import get_logger
from .acp import AcpAgent, AcpError
from .config import AgentConfig
from .provision import bot_owner_id
from .store import BridgeStore

logger = get_logger(__name__)

ZULIP_MESSAGE_LIMIT = 9500
TYPING_REFRESH_SECONDS = 8
HELP = (
    "Commands: `/status`, `/cancel` (stop the current turn), `/new` (start a fresh "
    "session), `/cwd PATH` (switch workspace; allowed directories only), "
    "`/approve ID`, `/deny ID`."
)
_YES = {"yes", "y", "approve", "allow", "ok", "/approve"}
_NO = {"no", "n", "deny", "reject", "/deny"}


def conversation_key(message: dict[str, Any], bot_id: int | None) -> str:
    if message.get("type") == "private":
        ids = sorted(
            person["id"]
            for person in message.get("display_recipient") or []
            if isinstance(person, dict) and person.get("id") != bot_id
        )
        return "dm:" + ",".join(str(i) for i in ids)
    return f"ch:{message['stream_id']}:{str(message.get('subject', '')).casefold()}"


def destination(message: dict[str, Any], bot_id: int | None) -> dict[str, Any]:
    if message.get("type") == "private":
        return {
            "type": "private",
            "to": sorted(
                person["id"]
                for person in message.get("display_recipient") or []
                if isinstance(person, dict) and person.get("id") != bot_id
            ),
        }
    return {
        "type": "stream",
        "to": message["stream_id"],
        "topic": message.get("subject"),
        "channel": message.get("display_recipient"),
    }


def strip_mention(content: str, bot_id: int | None, name: str | None) -> str:
    patterns = [rf"@_?\*\*{re.escape(name)}(\|\d+)?\*\*"] if name else []
    if bot_id is not None:
        patterns.append(rf"@_?\*\*[^*|]+\|{bot_id}\*\*")
    for pattern in patterns:
        content = re.sub(pattern, "", content)
    return content.strip()


def split_message(text: str, limit: int = ZULIP_MESSAGE_LIMIT) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        cut = cut if cut > limit // 2 else limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return [*parts, text] if text else parts


@dataclass
class Conversation:
    key: str
    destination: dict[str, Any]
    cwd: Path
    session_id: str | None = None
    agent: AcpAgent | None = None
    pending: list[dict[str, Any]] = field(default_factory=list)
    busy: bool = False
    last_active: float = field(default_factory=time.monotonic)
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


class AgentBridge:
    """Serve one agent bot until stopped."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.store = BridgeStore(config.state_path)
        manager = ConfigManager(config_file=str(config.zuliprc))
        self.client = ZulipClientWrapper(manager, use_bot_identity=False)
        self.fingerprint = manager.resolved_account().fingerprint
        self.inbox = BotMentionInbox(
            self.client,
            config.state_path.with_name(f"{config.name}-inbox.sqlite3"),
            self.fingerprint,
            ALL_SCOPE,
        )
        self.conversations: dict[str, Conversation] = {}
        self.owner_id: int | None = None
        self.bot_id: int | None = None
        self.bot_name: str | None = None
        self._stop = asyncio.Event()

    # Lifecycle
    async def run(self) -> None:
        profile = await asyncio.to_thread(self.client.client.get_profile)
        if profile.get("result") != "success" or not profile.get("is_bot"):
            raise RuntimeError(f"{self.config.name}: zuliprc must belong to a bot")
        self.bot_id, self.bot_name = profile["user_id"], profile.get("full_name")
        self.owner_id = await asyncio.to_thread(bot_owner_id, self.client)
        if self.owner_id is None:
            raise RuntimeError(f"{self.config.name}: the bot has no owner in Zulip")
        logger.info(
            "agent bot %s (%s) serving owner %s",
            self.config.name,
            self.bot_name,
            self.owner_id,
        )
        await self._report_interrupted_turns()
        reaper = asyncio.create_task(self._reap_idle())
        try:
            await self._listen()
        finally:
            reaper.cancel()
            await self.shutdown()

    def stop(self) -> None:
        self._stop.set()

    async def shutdown(self) -> None:
        for conversation in self.conversations.values():
            if conversation.task:
                conversation.task.cancel()
            if conversation.agent:
                await conversation.agent.close()
        self.inbox.stop()

    async def _listen(self) -> None:
        cursor = self.inbox.delivered_cursor()
        if cursor is None:
            # First start: begin from now, never replay old messages as work.
            start = 0
            while True:
                page = await asyncio.to_thread(self.inbox.poll, start, 50, 0)
                following = int(page.get("next_after_message_id") or start)
                if following <= start:
                    break
                start = following
            self.inbox.claim(None, start)
            cursor = self.inbox.delivered_cursor() or start
        while not self._stop.is_set():
            page = await asyncio.to_thread(self.inbox.poll, cursor, 50, 20)
            error = page.get("listener", {}).get("error")
            if error:
                logger.warning("%s listener: %s", self.config.name, error)
                await asyncio.sleep(
                    max(5, page["listener"].get("retry_after_seconds", 5))
                )
                continue
            messages = page.get("messages", [])
            advance = max(
                [cursor, int(page.get("next_after_message_id") or cursor)]
                + [m["id"] for m in messages]
            )
            if advance == cursor:
                continue
            if not self.inbox.claim(cursor, advance):
                cursor = self.inbox.delivered_cursor() or cursor
                continue
            cursor = advance
            for message in messages:
                await self.route(message)

    # Routing
    def admitted(self, message: dict[str, Any]) -> bool:
        sender = message.get("sender_id")
        return type(sender) is int and (
            sender == self.owner_id or sender in self.config.allow
        )

    async def route(self, message: dict[str, Any]) -> None:
        if not self.admitted(message):
            return  # strangers get nothing, not even a refusal
        key = conversation_key(message, self.bot_id)
        text = strip_mention(
            str(message.get("content", "")), self.bot_id, self.bot_name
        )
        question = self.store.open_question(key)
        direct = message.get("type") == "private"
        if not direct and "mentioned" not in message.get("flags", []) and not question:
            return  # owner chatter in a topic the bot watches for answers
        if await self._answer(key, text, question, message):
            return
        if text.startswith("/"):
            await self._command(key, text, message)
            return
        conversation = self._conversation(key, message)
        conversation.pending.append({**message, "text": text})
        conversation.wake.set()

    async def _answer(
        self,
        key: str,
        text: str,
        question: dict[str, Any] | None,
        message: dict[str, Any],
    ) -> bool:
        words = text.split()
        explicit = words[:1] in (["/approve"], ["/deny"]) and len(words) == 2
        if text.startswith("/") and not explicit:
            return False  # commands such as /cancel work while a request is open
        if explicit:
            question = self.store.question(words[1])
            if not question or question["key"] != key:
                await self._post_to(message, f"No open request `{words[1]}` here.")
                return True
        if not question:
            return False
        if question["kind"] == "permission":
            verdict = words[0].casefold() if words else ""
            if explicit:
                verdict = words[0]
            if verdict not in _YES | _NO:
                await self._post_to(
                    message,
                    f"Request `{question['id']}` is waiting: answer `yes` or `no`.",
                )
                return True
            answer = "allow" if verdict in _YES else "deny"
        else:
            answer = text
        if self.store.answer(question["id"], answer):
            await asyncio.to_thread(
                self.client.add_reaction, message["id"], "check_mark"
            )
        return True

    async def _command(self, key: str, text: str, message: dict[str, Any]) -> None:
        name, _, argument = text.partition(" ")
        conversation = self.conversations.get(key)
        if name == "/status":
            bound = self.store.conversation(key)
            state = (
                "working"
                if conversation and conversation.busy
                else "running" if conversation and conversation.agent else "stopped"
            )
            reply = (
                f"`{self.config.name}` is {state}. Session "
                f"`{(bound or {}).get('session_id') or 'none'}`, workspace "
                f"`{(bound or {}).get('cwd') or self.config.cwd}`"
                + (f", {len(conversation.pending)} queued." if conversation else ".")
            )
        elif name == "/cancel":
            if conversation and conversation.agent and conversation.session_id:
                await conversation.agent.cancel(conversation.session_id)
                reply = "Cancelling the current turn."
            else:
                reply = "Nothing is running."
        elif name == "/new":
            cwd = conversation.cwd if conversation else self.config.cwd
            await self._close(conversation)
            self.store.bind(key, None, str(cwd), destination(message, self.bot_id))
            reply = "The next message starts a fresh session."
        elif name == "/cwd":
            target = Path(os.path.expanduser(argument.strip() or "~")).resolve()
            if not self.config.permits_dir(target) or not target.is_dir():
                reply = "That directory is not in this agent's allowed_dirs."
            else:
                await self._close(conversation)
                self.store.bind(
                    key, None, str(target), destination(message, self.bot_id)
                )
                self.conversations.pop(key, None)
                reply = f"Workspace is now `{target}`; the next message starts there."
        else:
            reply = HELP
        await self._post_to(message, reply)

    # Conversations and turns
    def _conversation(self, key: str, message: dict[str, Any]) -> Conversation:
        conversation = self.conversations.get(key)
        if conversation is None:
            bound = self.store.conversation(key) or {}
            conversation = Conversation(
                key=key,
                destination=destination(message, self.bot_id),
                cwd=Path(bound.get("cwd") or self.config.cwd),
                session_id=bound.get("session_id"),
            )
            conversation.task = asyncio.create_task(self._worker(conversation))
            self.conversations[key] = conversation
            if conversation.destination["type"] == "stream":
                # Deliver unmentioned owner messages here so questions can be
                # answered in place; route() drops them otherwise.
                self.inbox.watch(
                    conversation.destination["to"], conversation.destination["topic"]
                )
        return conversation

    async def _worker(self, conversation: Conversation) -> None:
        while True:
            await conversation.wake.wait()
            conversation.wake.clear()
            if not conversation.pending:
                continue
            batch, conversation.pending = conversation.pending, []
            conversation.busy = True
            try:
                await self._turn(conversation, batch)
            except Exception as error:  # a failed turn must not kill the worker
                logger.exception("turn failed in %s", conversation.key)
                await self._post(conversation.destination, f"The agent failed: {error}")
            finally:
                conversation.busy = False
                conversation.last_active = time.monotonic()
            if conversation.pending:
                conversation.wake.set()

    async def _ensure_agent(self, conversation: Conversation) -> tuple[AcpAgent, bool]:
        if conversation.agent and conversation.agent.alive and conversation.session_id:
            return conversation.agent, False
        agent = AcpAgent(
            self.config.command,
            env=self._agent_env(),
            cwd=str(conversation.cwd),
            on_permission=lambda session_id, params: self._permission(
                conversation, params
            ),
        )
        await agent.start()
        previous = conversation.session_id
        conversation.session_id = await agent.open_session(
            str(conversation.cwd), self._mcp_servers(conversation), previous
        )
        conversation.agent = agent
        self.store.bind(
            conversation.key,
            conversation.session_id,
            str(conversation.cwd),
            conversation.destination,
        )
        return agent, conversation.session_id != previous

    async def _turn(
        self, conversation: Conversation, batch: list[dict[str, Any]]
    ) -> None:
        last = batch[-1]
        self.store.start_turn(last["id"], conversation.key)
        await asyncio.to_thread(self.client.add_reaction, last["id"], "eyes")
        typing = asyncio.create_task(self._typing(conversation.destination))
        try:
            agent, fresh = await self._ensure_agent(conversation)
            text = "\n\n".join(item["text"] for item in batch)
            if fresh:
                text = self._preface(conversation) + text
            result = await agent.prompt(conversation.session_id or "", text)
        except AcpError as error:
            conversation.agent = None
            self.store.finish_turn(last["id"], "failed")
            await self._post(conversation.destination, f"The agent stopped: {error}")
            return
        finally:
            typing.cancel()
            await self._typing_stop(conversation.destination)
        self.store.finish_turn(last["id"])
        if result.stop_reason == "cancelled":
            body = result.text.strip() or "Stopped."
        elif result.text.strip():
            body = result.text.strip()
        else:
            body = f"Finished ({result.stop_reason}) without a written answer."
        for part in split_message(body):
            await self._post(conversation.destination, part)

    def _preface(self, conversation: Conversation) -> str:
        where = (
            "a direct message"
            if conversation.destination["type"] == "private"
            else f"#{conversation.destination['channel']} > {conversation.destination['topic']}"
        )
        return (
            f"[You are reached through the Zulip bot {self.bot_name} in {where}. Your "
            "final answer is posted there as Markdown, so keep it concise. To ask the "
            "owner something mid-task, use the ask_owner tool.]\n\n"
        )

    async def _permission(
        self, conversation: Conversation, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Relay an ACP permission request to Zulip; silence means no."""
        options = params.get("options") or []
        tool = params.get("toolCall") or {}
        title = tool.get("title") or tool.get("kind") or "an action"
        question_id = self.store.ask(
            conversation.key,
            "permission",
            title,
            [option.get("optionId", "") for option in options],
            self.config.question_minutes,
        )
        await self._post(
            conversation.destination,
            f"**Permission request `{question_id}`**: {title}\n"
            f"Answer `yes` or `no`. No answer within "
            f"{self.config.question_minutes:g} min means no.",
        )
        deadline = time.monotonic() + self.config.question_minutes * 60
        answer = None
        while time.monotonic() < deadline and answer is None:
            await asyncio.sleep(1)
            answer = (self.store.question(question_id) or {}).get("answer")
        kinds = (
            ("allow_once", "allow_always")
            if answer == "allow"
            else ("reject_once", "reject_always")
        )
        for kind in kinds:
            for option in options:
                if option.get("kind") == kind:
                    return {
                        "outcome": {
                            "outcome": "selected",
                            "optionId": option["optionId"],
                        }
                    }
        return {"outcome": {"outcome": "cancelled"}}

    def _agent_env(self) -> dict[str, str]:
        # The agent never inherits the owner's Zulip credentials.
        env = {k: v for k, v in os.environ.items() if not k.startswith("ZULIP")}
        return {**env, **self.config.env}

    def _mcp_servers(self, conversation: Conversation) -> list[dict[str, Any]]:
        if not self.config.zulip_tools:
            return []
        return [
            {
                "name": "zulipchat",
                "command": sys.executable,
                "args": [
                    "-m",
                    "zulipchat_mcp.server",
                    "--zulip-config-file",
                    str(self.config.zuliprc),
                ],
                "env": [
                    {"name": "ZULIPCHAT_AGENT_STATE", "value": str(self.store.path)},
                    {"name": "ZULIPCHAT_AGENT_CONVERSATION", "value": conversation.key},
                    {
                        "name": "ZULIPCHAT_AGENT_QUESTION_MINUTES",
                        "value": f"{self.config.question_minutes:g}",
                    },
                ],
            }
        ]

    async def _close(self, conversation: Conversation | None) -> None:
        if conversation and conversation.agent:
            await conversation.agent.close()
            conversation.agent = None

    async def _reap_idle(self) -> None:
        while True:
            await asyncio.sleep(60)
            idle = self.config.idle_minutes * 60
            for conversation in self.conversations.values():
                if (
                    conversation.agent
                    and not conversation.busy
                    and time.monotonic() - conversation.last_active > idle
                ):
                    await self._close(conversation)

    async def _report_interrupted_turns(self) -> None:
        for turn in self.store.interrupted_turns():
            bound = self.store.conversation(turn["key"])
            if bound:
                await self._post(
                    bound["destination"],
                    "I was restarted while working on an earlier message, so that "
                    "work may be partial. Send it again if you still need it.",
                )
            self.store.finish_turn(turn["message_id"], "interrupted")

    # Zulip output
    async def _post(self, where: dict[str, Any], content: str) -> None:
        response = await asyncio.to_thread(
            self.client.send_message,
            where["type"],
            where["to"],
            content,
            where.get("topic"),
        )
        if response.get("result") != "success":
            logger.warning("post failed: %s", response.get("msg"))

    async def _post_to(self, message: dict[str, Any], content: str) -> None:
        await self._post(destination(message, self.bot_id), content)

    def _typing_request(self, where: dict[str, Any], op: str) -> dict[str, Any]:
        if where["type"] == "private":
            return {"op": op, "type": "direct", "to": where["to"]}
        return {
            "op": op,
            "type": "stream",
            "stream_id": where["to"],
            "topic": where["topic"],
        }

    async def _typing(self, where: dict[str, Any]) -> None:
        while True:
            await asyncio.to_thread(
                self.client.client.call_endpoint,
                url="typing",
                method="POST",
                request=self._typing_request(where, "start"),
            )
            await asyncio.sleep(TYPING_REFRESH_SECONDS)

    async def _typing_stop(self, where: dict[str, Any]) -> None:
        await asyncio.to_thread(
            self.client.client.call_endpoint,
            url="typing",
            method="POST",
            request=self._typing_request(where, "stop"),
        )
