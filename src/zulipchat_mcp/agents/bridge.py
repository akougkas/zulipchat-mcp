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
from .acp import WORKER_ASK_META, AcpAgent, AcpError
from .config import AgentConfig
from .provision import ProvisionError, bot_owner_id
from .store import BridgeStore

logger = get_logger(__name__)

ZULIP_MESSAGE_LIMIT = 9500
TYPING_REFRESH_SECONDS = 8
PROGRESS_DELAY_SECONDS = 20  # turns shorter than this post no status message
PROGRESS_EVERY_SECONDS = 10
REACTION_POLL_SECONDS = 3
# Reactions that answer a permission request, by Unicode emoji code.
_ALLOW_EMOJI = {"1f44d", "2705", "2714"}  # thumbs up, check marks
_DENY_EMOJI = {"1f44e", "274c", "1f6ab"}  # thumbs down, cross mark, no entry
HELP = (
    "Commands: `/status`, `/cancel` (stop the current turn), `/new` (start a fresh "
    "session), `/cwd PATH` (switch workspace; allowed directories only), "
    "`/approve ID`, `/deny ID`."
)
_YES = {"yes", "y", "approve", "allow", "ok", "/approve"}
_NO = {"no", "n", "deny", "reject", "/deny"}
DECISION_META = "clio-coder/decision"
MAX_ANSWER_CHARS = 16 * 1024


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


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _fenced(text: str, limit: int = 600) -> str:
    text = text if len(text) <= limit else text[:limit] + "…"
    return "```\n" + text.replace("```", "ˋˋˋ") + "\n```"


def describe_permission(params: dict[str, Any]) -> str:
    """Markdown for an ACP permission request, using Clio's decision facts if sent."""
    tool, meta = _dict(params.get("toolCall")), _dict(params.get("_meta"))
    decision, worker = _dict(meta.get(DECISION_META)), meta.get(WORKER_ASK_META)
    title = (
        decision.get("title") or tool.get("title") or tool.get("kind") or "an action"
    )
    lines = [str(title)]
    raw = _dict(tool.get("rawInput"))
    target = decision.get("target") or next(
        (
            str(raw[k])
            for k in ("command", "cmd", "file_path", "path", "url")
            if raw.get(k)
        ),
        None,
    )
    if not target:
        paths = [
            str(loc.get("path"))
            for loc in tool.get("locations") or []
            if _dict(loc).get("path")
        ]
        target = "\n".join(paths[:5]) or None
    if target and target != title:
        lines.append(_fenced(str(target)))
    lines += [f"- {line}" for line in decision.get("consequenceLines") or []]
    if isinstance(worker, dict):
        lines.append(
            f"Asked by worker `{worker.get('agentId') or worker.get('requestedBy')}`."
        )
    return "\n".join(lines)


def interview_answer(question: dict[str, Any], text: str) -> dict[str, Any]:
    """Map a reply onto Clio's answer contract: numbers or labels pick options."""
    labels = [str(o.get("label")) for o in question.get("options") or []]
    multi = question.get("multi_select") is True
    chosen: list[str] = []
    for pick in (text.split(",") if multi else [text]):
        pick = pick.strip().rstrip(".")
        if pick.isdigit() and 1 <= int(pick) <= len(labels):
            label = labels[int(pick) - 1]
        else:
            label = next((x for x in labels if x.casefold() == pick.casefold()), "")
        if not label:
            chosen = []
            break
        if label not in chosen:
            chosen.append(label)
    if chosen:
        return {
            "question": question["question"],
            "answer": "; ".join(chosen),
            "options": chosen,
        }
    return {"question": question["question"], "answer": text[:MAX_ANSWER_CHARS]}


def _line(text: Any, limit: int = 120) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _duration(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}m{seconds:02d}s" if minutes else f"{seconds}s"


@dataclass
class Progress:
    """What a running turn is doing, rendered into one status message."""

    started: float = field(default_factory=time.monotonic)
    calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    plan: list[dict[str, Any]] = field(default_factory=list)
    message_id: int | None = None

    def update(self, update: dict[str, Any]) -> None:
        kind = update.get("sessionUpdate")
        if kind in ("tool_call", "tool_call_update"):
            call = self.calls.setdefault(str(update.get("toolCallId")), {})
            for key in ("title", "status"):
                if update.get(key) is not None:
                    call[key] = update[key]
        elif kind == "plan":
            self.plan = [e for e in update.get("entries") or [] if isinstance(e, dict)]

    def render(self, done: bool = False) -> str:
        elapsed = _duration(time.monotonic() - self.started)
        count = len(self.calls)
        calls = f"{count} tool call{'' if count == 1 else 's'}"
        if done:
            return f"Finished in {elapsed} · {calls}."
        lines = [f"⏳ Working {elapsed} · {calls}"]
        running = [
            call
            for call in self.calls.values()
            if call.get("status") in (None, "pending", "in_progress")
        ]
        current = (running or list(self.calls.values()) or [{}])[-1]
        if current.get("title"):
            lines.append(f"▸ {_line(current['title'])}")
        marks = {"completed": "✔", "in_progress": "▸"}
        for entry in self.plan[:10]:
            mark = marks.get(entry.get("status", ""), "☐")
            lines.append(f"{mark} {_line(entry.get('content'), 100)}")
        return "\n".join(lines)


@dataclass
class Conversation:
    key: str
    destination: dict[str, Any]
    cwd: Path
    session_id: str | None = None
    prefaced: bool = False  # this session has been told it is reached via Zulip
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
        try:
            self.owner_id = await asyncio.to_thread(bot_owner_id, self.client)
        except ProvisionError as error:
            raise RuntimeError(f"{self.config.name}: {error}") from error
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
        await self._reconcile(conversation)
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

    async def _reconcile(self, conversation: Conversation) -> None:
        """Adopt a binding changed outside this conversation (/new, teleport)."""
        if conversation.busy:
            return
        bound = self.store.conversation(conversation.key)
        if not bound:
            return
        session_id, cwd = bound.get("session_id"), Path(bound["cwd"])
        if session_id != conversation.session_id or cwd != conversation.cwd:
            await self._close(conversation)
            conversation.session_id, conversation.cwd = session_id, cwd
            conversation.prefaced = False

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
            self._agent_command(),
            env=self.config.agent_env(),
            cwd=str(conversation.cwd),
            on_permission=lambda session_id, params: self._permission(
                conversation, params
            ),
            on_interview=lambda session_id, params: self._interview(
                conversation, params
            ),
        )
        await agent.start()
        previous = conversation.session_id
        servers = self._mcp_servers(conversation)
        try:
            conversation.session_id = await agent.open_session(
                str(conversation.cwd), servers, previous
            )
        except AcpError:
            if previous is None:
                raise
            # Some agents hang or exit on a session they no longer know
            # (goose); start over with a fresh process and a new session.
            logger.warning("%s could not reopen %s", self.config.name, previous)
            await agent.close()
            await agent.start()
            conversation.session_id = await agent.open_session(
                str(conversation.cwd), servers, None
            )
        conversation.agent = agent
        self.store.bind(
            conversation.key,
            conversation.session_id,
            str(conversation.cwd),
            conversation.destination,
        )
        if conversation.session_id != previous:
            conversation.prefaced = False
        return agent, conversation.session_id != previous

    async def _turn(
        self, conversation: Conversation, batch: list[dict[str, Any]]
    ) -> None:
        last = batch[-1]
        self.store.start_turn(last["id"], conversation.key)
        await asyncio.to_thread(self.client.add_reaction, last["id"], "eyes")
        typing = asyncio.create_task(self._typing(conversation.destination))
        progress = Progress()
        status = asyncio.create_task(self._progress(conversation.destination, progress))
        try:
            agent, _ = await self._ensure_agent(conversation)
            text = "\n\n".join(item["text"] for item in batch)
            if not conversation.prefaced:
                # New, resumed after a restart, or teleported from a terminal.
                text = self._preface(conversation) + text
                conversation.prefaced = True
            result = await agent.prompt(
                conversation.session_id or "", text, on_update=progress.update
            )
        except AcpError as error:
            conversation.agent = None
            self.store.finish_turn(last["id"], "failed")
            await self._post(
                conversation.destination, f"The agent could not start: {error}"
            )
            return
        finally:
            typing.cancel()
            status.cancel()
            await self._typing_stop(conversation.destination)
            if progress.message_id is not None:
                await self._edit(progress.message_id, progress.render(done=True))
        self.store.finish_turn(last["id"], "failed" if result.error else "done")
        if not agent.alive:
            conversation.agent = None
        if result.stop_reason == "error":
            body = (result.text.strip() + "\n\n" if result.text.strip() else "") + (
                f"The agent failed: {result.error}"
            )
        elif result.stop_reason == "cancelled":
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

    async def _ask(
        self,
        conversation: Conversation,
        kind: str,
        label: str,
        body: str,
        options: list[str],
    ) -> str | None:
        """Post a question and wait for the owner; None when silent or withdrawn.

        An unanswered question is closed on the way out, so a withdrawn or
        expired request never swallows the owner's next message.
        """
        minutes = self.config.question_minutes
        question_id = self.store.ask(conversation.key, kind, body, options, minutes)
        message_id = await self._post(
            conversation.destination, f"**{label} `{question_id}`**: {body}"
        )
        react_to = message_id if kind == "permission" else None
        if react_to is not None:
            for emoji in ("thumbs_up", "thumbs_down"):  # one click to answer
                await asyncio.to_thread(self.client.add_reaction, react_to, emoji)
        deadline = time.monotonic() + minutes * 60
        answer = None
        try:
            tick = 0
            while time.monotonic() < deadline and answer is None:
                await asyncio.sleep(1)
                tick += 1
                answer = (self.store.question(question_id) or {}).get("answer")
                if (
                    answer is None
                    and react_to is not None
                    and tick % REACTION_POLL_SECONDS == 0
                ):
                    verdict = await self._reaction_verdict(react_to)
                    if verdict and self.store.answer(question_id, verdict):
                        answer = verdict
        except asyncio.CancelledError:
            if self.store.close(question_id):
                await self._post(
                    conversation.destination,
                    f"Request `{question_id}` was withdrawn; no answer is needed.",
                )
            raise
        if answer is None and self.store.close(question_id):
            await self._post(
                conversation.destination,
                f"Request `{question_id}` expired unanswered.",
            )
        return answer

    async def _permission(
        self, conversation: Conversation, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Relay an ACP permission request to Zulip; silence means no."""
        options = params.get("options") or []
        body = (
            describe_permission(params)
            + "\nAnswer `yes` or `no`, or react 👍 or 👎. No answer within "
            + f"{self.config.question_minutes:g} min means no."
        )
        answer = await self._ask(
            conversation,
            "permission",
            "Permission request",
            body,
            [option.get("optionId", "") for option in options],
        )
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

    async def _interview(
        self, conversation: Conversation, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Ask a Clio interview round in Zulip, one question at a time."""
        answers = []
        for question in params.get("questions") or []:
            options = question.get("options") or []
            lines = [str(question.get("question", ""))]
            for number, option in enumerate(options, 1):
                described = (
                    f": {option['description']}" if option.get("description") else ""
                )
                lines.append(f"{number}. **{option.get('label')}**{described}")
            if options:
                lines.append(
                    "Reply with a number or label"
                    + (
                        " (several, comma-separated)"
                        if question.get("multi_select")
                        else ""
                    )
                    + ", or answer in your own words."
                )
            header = question.get("header")
            answer = await self._ask(
                conversation,
                "interview",
                f"Question{' (' + str(header) + ')' if header else ''}",
                "\n".join(lines),
                [str(option.get("label")) for option in options],
            )
            if not answer or not answer.strip():
                return {"cancelled": True}
            answers.append(interview_answer(question, answer.strip()))
        return {"answers": answers} if answers else {"cancelled": True}

    async def _reaction_verdict(self, message_id: int) -> str | None:
        """allow or deny from the owner's reaction on a request, if any."""
        response: dict[str, Any] = await asyncio.to_thread(
            self.client.client.get_raw_message, message_id
        )
        for reaction in _dict(response.get("message")).get("reactions") or []:
            if not self.admitted({"sender_id": reaction.get("user_id")}):
                continue
            if reaction.get("emoji_code") in _ALLOW_EMOJI:
                return "allow"
            if reaction.get("emoji_code") in _DENY_EMOJI:
                return "deny"
        return None

    def _agent_command(self) -> list[str]:
        command = list(self.config.command)
        # Clio stops waiting on a permission or interview after
        # --permission-timeout (2 min by default); match the Zulip question window.
        if (
            Path(command[0]).name == "clio-coder"
            and "acp" in command
            and "--permission-timeout" not in command
        ):
            minutes = self.config.question_minutes
            command += ["--permission-timeout", str(int(minutes * 60_000))]
        return command

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
    async def _post(self, where: dict[str, Any], content: str) -> int | None:
        response = await asyncio.to_thread(
            self.client.send_message,
            where["type"],
            where["to"],
            content,
            where.get("topic"),
        )
        if response.get("result") != "success":
            logger.warning("post failed: %s", response.get("msg"))
            return None
        message_id = response.get("id")
        return message_id if type(message_id) is int else None

    async def _edit(self, message_id: int, content: str) -> bool:
        response = await asyncio.to_thread(
            self.client.client.update_message,
            {"message_id": message_id, "content": content},
        )
        if response.get("result") != "success":
            logger.debug("status edit failed: %s", response.get("msg"))
        return response.get("result") == "success"

    async def _progress(self, where: dict[str, Any], progress: Progress) -> None:
        """Keep one status message current; never more than one per edit window."""
        await asyncio.sleep(PROGRESS_DELAY_SECONDS)
        progress.message_id = await self._post(where, progress.render())
        fresh = True
        while progress.message_id is not None:
            await asyncio.sleep(PROGRESS_EVERY_SECONDS)
            if await self._edit(progress.message_id, progress.render()):
                fresh = False
            elif fresh:
                return  # the realm does not let this bot edit; one status is enough
            else:  # past the realm's edit time limit: continue in a new message
                progress.message_id = await self._post(where, progress.render())
                fresh = True

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
