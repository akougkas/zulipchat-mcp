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

from ..config import ConfigManager, load_zuliprc_credentials
from ..core.client import OUTBOUND_CLIENT_NAME, ZulipClientWrapper
from ..services.bot_mentions import ALL_SCOPE, BotMentionInbox
from ..utils.logging import get_logger
from ..utils.redaction import redact, secret_values
from .acp import WORKER_ASK_META, AcpAgent, AcpError
from .config import AgentConfig
from .provision import ProvisionError, bot_owner_id
from .store import BridgeStore

logger = get_logger(__name__)

ZULIP_MESSAGE_LIMIT = 9500
MAX_ANSWER_PARTS = 5  # one answer never floods a conversation
PERMISSION_TARGET_LIMIT = 6000  # the approver must see what they approve
OWNER_CHECK_SECONDS = 300
OFFLINE_RETRY_SECONDS = (5, 300)  # first and longest wait to reach Zulip at start
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
INTERVIEW_META = "clio-coder/interview"
MAX_ANSWER_CHARS = 16 * 1024


class BridgeConfigError(RuntimeError):
    """Restarting cannot fix this: the zuliprc, the bot or its owner is wrong."""


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


def _fenced(text: str, limit: int = PERMISSION_TARGET_LIMIT) -> str:
    block = "```\n" + text[:limit].replace("```", "ˋˋˋ") + "\n```"
    if len(text) > limit:
        # Never let an approval cover text the approver could not read.
        block += (
            f"\n⚠️ Only the first {limit} of {len(text)} characters are shown. "
            "Answer `no` unless you know the rest."
        )
    return block


_MENTION = re.compile(r"@(?=\*)")


def silence_mentions(text: str) -> str:
    """Make every mention silent outside code blocks, so agent text pings nobody."""
    parts = text.split("```")
    parts[::2] = [_MENTION.sub("@_", part) for part in parts[::2]]
    return "```".join(parts)


def known_secrets(config: AgentConfig) -> list[str]:
    """Secret values this process can see: they must never be posted to Zulip."""
    try:
        bot_key = load_zuliprc_credentials(str(config.zuliprc))["api_key"]
    except (OSError, ValueError, KeyError, LookupError):
        bot_key = None  # the client reports an unusable zuliprc
    return secret_values(os.environ, config.env, extra=[bot_key])


def describe_permission(params: dict[str, Any]) -> str:
    """Markdown for an ACP permission request, using Clio's decision facts if sent."""
    tool, meta = _dict(params.get("toolCall")), _dict(params.get("_meta"))
    decision, worker = _dict(meta.get(DECISION_META)), meta.get(WORKER_ASK_META)
    title = str(
        decision.get("title") or tool.get("title") or tool.get("kind") or "an action"
    )
    lines = [_line(title, 300)]
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
    lines += [
        f"- {_line(line, 300)}"
        for line in (decision.get("consequenceLines") or [])[:10]
    ]
    if isinstance(worker, dict):
        lines.append(
            f"Asked by worker `{worker.get('agentId') or worker.get('requestedBy')}`."
        )
    return "\n".join(lines)


def exact_choice(question: dict[str, Any], text: str) -> bool:
    """Whether text is nothing but a valid choice for an open request."""
    words = text.split()
    if words[:1] in (["/approve"], ["/deny"]) and len(words) == 2:
        return True
    if question.get("kind") == "permission":
        return text.strip().rstrip(".!").casefold() in _YES | _NO
    labels = [str(label).casefold() for label in question.get("options") or []]
    picks = [pick.strip().rstrip(".").casefold() for pick in text.split(",")]
    return bool(labels) and all(
        pick in labels or (pick.isdigit() and 1 <= int(pick) <= len(labels))
        for pick in picks
    )


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

    def __init__(self, config: AgentConfig, accept_owner: bool = False) -> None:
        self.config = config
        self.accept_owner = accept_owner
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
        self.secrets = known_secrets(config)
        self._verdicts: dict[str, str] = {}  # answers taken from Zulip, by question
        self._revoked = False
        self.owner_id: int | None = None
        self.bot_id: int | None = None
        self.bot_name: str | None = None
        self._stop = asyncio.Event()

    # Lifecycle
    def _whoami(self) -> tuple[dict[str, Any], int | None] | None:
        """The bot's profile and owner, or None while Zulip is unreachable."""
        try:
            profile = self.client.client.get_profile()
            if profile.get("result") == "error" and profile.get("code") != (
                "RATE_LIMIT_HIT"
            ):
                raise BridgeConfigError(
                    f"{self.config.name}: Zulip refused the zuliprc: {profile.get('msg')}"
                )
            if profile.get("result") != "success":
                return None  # a server error page or rate limit
            if not profile.get("is_bot"):
                raise BridgeConfigError(
                    f"{self.config.name}: zuliprc must belong to a bot"
                )
            return profile, bot_owner_id(self.client)
        except ProvisionError as error:
            raise BridgeConfigError(f"{self.config.name}: {error}") from error
        except BridgeConfigError:
            raise
        except Exception as error:  # offline, DNS, TLS, the server restarting
            logger.warning("%s cannot reach Zulip: %s", self.config.name, error)
            return None

    async def run(self) -> None:
        delay, longest = OFFLINE_RETRY_SECONDS
        # A laptop starts the service before its network is up: wait, never exit.
        while (found := await asyncio.to_thread(self._whoami)) is None:
            try:
                await asyncio.wait_for(self._stop.wait(), delay)
                return
            except asyncio.TimeoutError:
                delay = min(delay * 2, longest)
        profile, self.owner_id = found
        self.bot_id, self.bot_name = profile["user_id"], profile.get("full_name")
        if self.owner_id is None:
            raise BridgeConfigError(
                f"{self.config.name}: the bot has no owner in Zulip"
            )
        # An organization administrator can reassign a bot. The owner drives a
        # local agent, so a new owner is never adopted from Zulip silently.
        paired = self.store.owner()
        if paired is None or self.accept_owner:
            self.store.pair_owner(self.owner_id)
        elif paired != self.owner_id:
            raise BridgeConfigError(self._owner_changed(paired, self.owner_id))
        logger.info(
            "agent bot %s (%s) serving owner %s",
            self.config.name,
            self.bot_name,
            self.owner_id,
        )
        await self._report_interrupted_turns()
        serving = self.owner_id
        reaper = asyncio.create_task(self._reap_idle())
        watcher = asyncio.create_task(self._watch_owner())
        try:
            await self._listen()
        finally:
            reaper.cancel()
            watcher.cancel()
            await self.shutdown()
        if self.owner_id != serving:
            raise BridgeConfigError(self._owner_changed(serving, self.owner_id))

    def _owner_changed(self, paired: int, current: int | None) -> str:
        return (
            f"{self.config.name}: Zulip reports user {current} as this bot's owner, "
            f"but the bridge is paired with user {paired}. Nobody is served. If you "
            "changed the owner yourself, start once with "
            "`zulipchat-mcp-agents run --accept-owner`."
        )

    async def _watch_owner(self) -> None:
        """Stop serving as soon as the bot's owner in Zulip is someone else."""
        while True:
            await asyncio.sleep(OWNER_CHECK_SECONDS)
            try:
                current = await asyncio.to_thread(bot_owner_id, self.client)
            except Exception as error:  # an outage is not an owner change
                logger.warning("%s owner check failed: %s", self.config.name, error)
                continue
            if current != self.owner_id:
                logger.error("%s: bot owner changed; stopping", self.config.name)
                self.owner_id = current
                self._revoked = True
                self.stop()
                return

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
            # Delivered or dropped, a message is never read again: keep no copy
            # of what strangers wrote to the bot.
            self.inbox.forget(cursor)

    # Routing
    def admitted(self, message: dict[str, Any]) -> bool:
        sender = message.get("sender_id")
        return (
            not self._revoked
            and type(sender) is int
            and (sender == self.owner_id or sender in self.config.allow)
            # Sent through this package's MCP server: an agent using the owner's
            # account, not the owner. It never prompts or answers an agent.
            and message.get("client") != OUTBOUND_CLIENT_NAME
        )

    async def route(self, message: dict[str, Any]) -> None:
        if not self.admitted(message):
            return  # strangers get nothing, not even a refusal
        key = conversation_key(message, self.bot_id)
        question = self.store.open_question(key)
        addressed = message.get("type") == "private" or "mentioned" in message.get(
            "flags", []
        )
        content = str(message.get("content", ""))
        # In a topic every message for the bot mentions it. The one exception is
        # an exact choice for the open request; anything else there is the
        # owner talking to other people and is never taken as an answer.
        if not addressed and not (question and exact_choice(question, content)):
            return
        if message.get("content_truncated"):
            # The inbox keeps 6000 characters; half an instruction is not one.
            full = await asyncio.to_thread(
                self.client.get_message, message["id"], apply_markdown=False, fresh=True
            )
            fetched = _dict(_dict(full).get("message")).get("content")
            if not isinstance(fetched, str):
                await self._post_to(
                    message,
                    "I could not read that long message in full, so I did not act "
                    "on it. Send it again in shorter parts.",
                )
                return
            content = fetched
        text = strip_mention(content, self.bot_id, self.bot_name)
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
            # The whole message must be the verdict: "ok, looking" said to a
            # colleague in the same topic approves nothing.
            verdict = words[0] if explicit else text.strip().rstrip(".!").casefold()
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
            self._verdicts[question["id"]] = answer
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
            # The agent waits for an answer as long as the question stays open
            # in Zulip; Clio's own default is two minutes.
            ask_timeout_ms=int(self.config.question_minutes * 60_000),
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
        mode = self._session_mode()
        if mode:
            # Fails closed: a mode the agent does not offer stops the turn.
            await agent.set_mode(conversation.session_id, mode)
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
        parts = split_message(body)
        if len(parts) > MAX_ANSWER_PARTS:
            dropped = sum(len(part) for part in parts[MAX_ANSWER_PARTS:])
            parts = [
                *parts[:MAX_ANSWER_PARTS],
                f"… {dropped} more characters were not posted.",
            ]
        for part in parts:
            await self._post(conversation.destination, part)

    def _preface(self, conversation: Conversation) -> str:
        where = (
            "a direct message"
            if conversation.destination["type"] == "private"
            else f"#{conversation.destination['channel']} > {conversation.destination['topic']}"
        )
        return (
            f"[You are reached through the Zulip bot {self.bot_name} in {where}. Your "
            "final answer is posted there as Markdown, so keep it concise."
            + (
                " To ask the owner something mid-task, use the ask_owner tool."
                if self.config.zulip_tools
                else ""
            )
            + "]\n\n"
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
                # Only an answer this process took from Zulip counts. The store
                # is a file the agent can write, so it never decides a request.
                answer = self._verdicts.pop(question_id, None)
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
        offered = {_dict(option).get("kind") for option in options}
        body = (
            describe_permission(params)
            + (
                "\n⚠️ The agent offers no one-time approval: `yes` allows this kind "
                "of action from now on."
                if "allow_always" in offered and "allow_once" not in offered
                else ""
            )
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
        # Clio names, per question, the option index it would take for an
        # absent operator.
        recommended = _dict(_dict(params.get("_meta")).get(INTERVIEW_META)).get(
            "recommended"
        )
        recommended = recommended if isinstance(recommended, list) else []
        for position, question in enumerate(params.get("questions") or []):
            options = question.get("options") or []
            preferred = recommended[position] if position < len(recommended) else None
            lines = [str(question.get("question", ""))]
            for number, option in enumerate(options, 1):
                described = (
                    f": {option['description']}" if option.get("description") else ""
                )
                marked = " (recommended)" if preferred == number - 1 else ""
                lines.append(f"{number}. **{option.get('label')}**{described}{marked}")
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
        # A person in Zulip is not at the keyboard. Clio is held to its default
        # autonomy, so it asks before acting, unless the file names a level
        # itself. The flag can lower Clio's configured level, never raise it.
        if (
            Path(command[0]).name == "clio-coder"
            and "acp" in command
            and "--autonomy" not in command
        ):
            command += ["--autonomy", "default"]
        return command

    def _session_mode(self) -> str | None:
        """The ACP session mode the bridge asks for, if any.

        Claude Code starts in auto mode, which never asks. A person in Zulip is
        not at the keyboard, so it runs in default mode, which asks before
        edits and commands, unless the file names a mode ("" keeps Claude's).
        """
        if self.config.mode is not None:
            return self.config.mode or None
        if Path(self.config.command[0]).name == "claude-agent-acp":
            return "default"
        return None

    def _mcp_servers(self, conversation: Conversation) -> list[dict[str, Any]]:
        if not self.config.zulip_tools:
            return []
        # "ask" gives the agent a way to reach its owner and nothing that reads
        # other people's messages or writes anywhere else.
        profile = (
            ["--tool-profile", "ask-owner"] if self.config.zulip_tools == "ask" else []
        )
        return [
            {
                "name": "zulipchat",
                "command": sys.executable,
                "args": [
                    "-m",
                    "zulipchat_mcp.server",
                    "--zulip-config-file",
                    str(self.config.zuliprc),
                    *profile,
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
    def _outbound(self, content: str) -> str:
        """Everything posted for an agent: no live mentions, no known secrets."""
        return silence_mentions(redact(content, self.secrets))

    async def _post(self, where: dict[str, Any], content: str) -> int | None:
        content = self._outbound(content)
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
            {"message_id": message_id, "content": self._outbound(content)},
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
