"""Asyncio client for the Agent Client Protocol (ACP) version 1.

The agent runs as a subprocess speaking newline-delimited JSON-RPC 2.0 on
stdio. Requests flow both ways: one reader task demultiplexes responses,
``session/update`` notifications and agent-to-client requests.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from .. import __version__
from ..utils.logging import get_logger

logger = get_logger(__name__)

PROTOCOL_VERSION = 1
MAX_LINE_BYTES = 8 * 1024 * 1024
TERMINATE_GRACE_SECONDS = 5.0
_DEFAULT_TIMEOUT = -1.0

PermissionHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
UpdateHandler = Callable[[dict[str, Any]], None]

_RPC_CODES = {
    -32000: "auth_required",
    -32002: "resource_not_found",
    -32601: "method_not_found",
    -32602: "invalid_params",
}
_CANCELLED: dict[str, Any] = {"outcome": {"outcome": "cancelled"}}


class AcpError(Exception):
    """An ACP failure with a stable string ``code`` and optional ``data``."""

    def __init__(self, code: str, message: str = "", data: Any = None) -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.data = data


@dataclass
class PromptResult:
    stop_reason: str
    text: str
    tool_calls: list[dict[str, Any]]
    error: str | None = None


@dataclass
class _Turn:
    on_update: UpdateHandler | None
    chunks: list[str] = field(default_factory=list)
    tool_calls: dict[str, dict[str, Any]] = field(default_factory=dict)

    def apply(self, update: dict[str, Any]) -> None:
        kind = update.get("sessionUpdate")
        if kind == "agent_message_chunk":
            content = update.get("content") or {}
            if content.get("type") == "text":
                self.chunks.append(str(content.get("text", "")))
        elif kind in ("tool_call", "tool_call_update"):
            call_id = str(update.get("toolCallId", ""))
            call = self.tool_calls.setdefault(
                call_id, {"id": call_id, "title": None, "kind": None, "status": None}
            )
            for key in ("title", "kind", "status"):
                if update.get(key) is not None:
                    call[key] = update[key]
        if self.on_update is not None:
            try:
                self.on_update(update)
            except Exception:
                logger.exception("ACP on_update callback failed")


def _reject_option(params: dict[str, Any]) -> dict[str, Any]:
    for option in params.get("options") or []:
        if "reject_once" in (option.get("kind"), option.get("optionId")):
            return {"outcome": {"outcome": "selected", "optionId": option["optionId"]}}
    return _CANCELLED


class AcpAgent:
    """One ACP agent subprocess and the sessions opened on it."""

    def __init__(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        on_permission: PermissionHandler | None = None,
        request_timeout: float = 120.0,
    ) -> None:
        self.command = list(command)
        self.env = env
        self.cwd = cwd
        self.on_permission = on_permission
        self.request_timeout = request_timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._capabilities: dict[str, Any] = {}
        self._next_id = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._turns: dict[str, _Turn] = {}
        self._loading: set[str] = set()
        self._sessions: set[str] = set()
        self._permission_tasks: dict[str, set[asyncio.Future[dict[str, Any]]]] = {}
        self._background: set[asyncio.Task[None]] = set()
        self._write_lock = asyncio.Lock()
        self._stderr_tail: deque[str] = deque(maxlen=20)
        self._exited = False

    @property
    def alive(self) -> bool:
        return (
            self._proc is not None
            and not self._exited
            and self._proc.returncode is None
        )

    @property
    def capabilities(self) -> dict[str, Any]:
        return self._capabilities

    async def start(self) -> dict[str, Any]:
        """Spawn the agent, run ``initialize`` and return its agentCapabilities."""
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
                cwd=self.cwd,
                limit=MAX_LINE_BYTES,
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            raise AcpError("spawn_failed", f"{self.command[0]}: {exc}") from exc
        self._spawn(self._read_stdout())
        self._spawn(self._read_stderr())
        result = await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                },
                "clientInfo": {"name": "zulipchat-mcp", "version": __version__},
            },
        )
        version = result.get("protocolVersion")
        if version != PROTOCOL_VERSION:
            await self.close()
            raise AcpError(
                "protocol_version", f"agent speaks ACP {version!r}", data=result
            )
        self._capabilities = result.get("agentCapabilities") or {}
        return self._capabilities

    async def open_session(
        self,
        cwd: str,
        mcp_servers: list[dict[str, Any]],
        session_id: str | None = None,
    ) -> str:
        """Resume or load ``session_id`` when supported, else create a session."""
        params = {"cwd": cwd, "mcpServers": mcp_servers}
        if session_id:
            session_caps = self._capabilities.get("sessionCapabilities") or {}
            method = None
            if session_caps.get("resume") not in (None, False):
                method = "session/resume"
            elif self._capabilities.get("loadSession"):
                method = "session/load"
            if method is not None:
                if method == "session/load":
                    self._loading.add(session_id)
                try:
                    await self._request(method, {"sessionId": session_id, **params})
                    self._sessions.add(session_id)
                    return session_id
                except AcpError as exc:
                    if exc.code == "agent_exited":
                        raise
                    logger.warning(
                        "ACP %s of %s failed, starting a new session: %s",
                        method,
                        session_id,
                        exc,
                    )
                finally:
                    self._loading.discard(session_id)
        result = await self._request("session/new", params)
        new_id = str(result["sessionId"])
        self._sessions.add(new_id)
        return new_id

    async def prompt(
        self,
        session_id: str,
        text: str,
        on_update: UpdateHandler | None = None,
    ) -> PromptResult:
        """Run one turn. Agent and transport failures return stop_reason "error"."""
        if session_id in self._turns:
            raise AcpError("busy", f"session {session_id} already has a turn running")
        turn = _Turn(on_update)
        self._turns[session_id] = turn
        try:
            result = await self._request(
                "session/prompt",
                {"sessionId": session_id, "prompt": [{"type": "text", "text": text}]},
                timeout=None,
            )
            stop_reason, error = str(result.get("stopReason", "end_turn")), None
        except AcpError as exc:
            stop_reason, error = "error", str(exc)
        finally:
            self._turns.pop(session_id, None)
        return PromptResult(
            stop_reason=stop_reason,
            text="".join(turn.chunks),
            tool_calls=list(turn.tool_calls.values()),
            error=error,
        )

    async def cancel(self, session_id: str) -> None:
        """Send ``session/cancel`` and answer pending permission requests cancelled."""
        for task in list(self._permission_tasks.get(session_id, ())):
            task.cancel()
        with contextlib.suppress(AcpError):
            await self._send(
                {"method": "session/cancel", "params": {"sessionId": session_id}}
            )

    async def close(self) -> None:
        """Close advertised sessions, then SIGTERM the agent and kill it after 5 s."""
        session_caps = self._capabilities.get("sessionCapabilities") or {}
        if self.alive and session_caps.get("close") not in (None, False):
            for session_id in list(self._sessions):
                try:
                    await self._request(
                        "session/close",
                        {"sessionId": session_id},
                        timeout=min(self.request_timeout, TERMINATE_GRACE_SECONDS),
                    )
                except AcpError as exc:
                    logger.debug("ACP session/close %s failed: %s", session_id, exc)
        self._sessions.clear()
        for handlers in self._permission_tasks.values():
            for handler in handlers:
                handler.cancel()
        proc = self._proc
        if proc is not None and proc.returncode is None:
            if proc.stdin is not None:
                with contextlib.suppress(Exception):
                    proc.stdin.close()
            self._signal(proc, signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), TERMINATE_GRACE_SECONDS)
            except asyncio.TimeoutError:
                self._signal(proc, signal.SIGKILL)
                await proc.wait()
        background = list(self._background)
        for task in background:
            task.cancel()
        await asyncio.gather(*background, return_exceptions=True)
        self._mark_exited()

    @staticmethod
    def _signal(proc: asyncio.subprocess.Process, sig: signal.Signals) -> None:
        with contextlib.suppress(ProcessLookupError):
            if os.name == "posix":
                os.killpg(proc.pid, sig)
            elif sig == signal.SIGTERM:
                proc.terminate()
            else:
                proc.kill()

    async def _request(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float | None = _DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Send a request and await its result; ``timeout=None`` waits forever."""
        if not self.alive:
            raise self._exit_error()
        self._next_id += 1
        request_id = self._next_id
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._send({"id": request_id, "method": method, "params": params})
            limit = self.request_timeout if timeout == _DEFAULT_TIMEOUT else timeout
            try:
                result = await asyncio.wait_for(future, limit)
            except asyncio.TimeoutError as exc:
                raise AcpError("timeout", f"{method} after {limit}s") from exc
        finally:
            self._pending.pop(request_id, None)
        return result if isinstance(result, dict) else {}

    async def _send(self, message: dict[str, Any]) -> None:
        proc = self._proc
        if not self.alive or proc is None or proc.stdin is None:
            raise self._exit_error()
        data = json.dumps({"jsonrpc": "2.0", **message}).encode() + b"\n"
        async with self._write_lock:
            try:
                proc.stdin.write(data)
                await proc.stdin.drain()
            except (ConnectionError, RuntimeError) as exc:
                raise self._exit_error() from exc

    def _exit_error(self) -> AcpError:
        returncode = self._proc.returncode if self._proc is not None else None
        return AcpError(
            "agent_exited",
            f"agent process is not running (returncode {returncode})",
            data={"returncode": returncode, "stderr": list(self._stderr_tail)},
        )

    def _mark_exited(self) -> None:
        self._exited = True
        error = self._exit_error()
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()

    async def _read_line(self, reader: asyncio.StreamReader) -> bytes | None:
        skipping = False
        while True:
            try:
                line = await reader.readuntil(b"\n")
            except asyncio.IncompleteReadError as exc:
                return exc.partial if exc.partial and not skipping else None
            except asyncio.LimitOverrunError as exc:
                await reader.readexactly(max(exc.consumed, 1))
                skipping = True
                continue
            if not skipping:
                return line
            logger.warning(
                "ACP agent sent a line over %d bytes; skipped", MAX_LINE_BYTES
            )
            skipping = False

    async def _read_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        reader = self._proc.stdout
        try:
            while (line := await self._read_line(reader)) is not None:
                if not line.strip():
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    logger.warning("ACP agent wrote non-JSON stdout: %.200r", line)
                    continue
                if isinstance(message, dict):
                    await self._dispatch(message)
        except Exception:
            logger.exception("ACP reader failed")
        finally:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._proc.wait(), TERMINATE_GRACE_SECONDS)
            self._mark_exited()

    async def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        reader = self._proc.stderr
        while (line := await self._read_line(reader)) is not None:
            text = line.decode(errors="replace").rstrip()
            if text:
                self._stderr_tail.append(text)
                logger.debug("ACP agent stderr: %s", text)

    async def _dispatch(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method is None:
            future = self._pending.get(message.get("id", 0))
            if future is None or future.done():
                return
            error = message.get("error")
            if error is not None:
                error = error if isinstance(error, dict) else {}
                code = error.get("code", 0)
                future.set_exception(
                    AcpError(
                        _RPC_CODES.get(code, "rpc_error"),
                        str(error.get("message", "")),
                        data={"rpc_code": code, "data": error.get("data")},
                    )
                )
            else:
                future.set_result(message.get("result"))
            return
        params = message.get("params")
        params = params if isinstance(params, dict) else {}
        if "id" not in message:
            if method == "session/update":
                session_id = str(params.get("sessionId", ""))
                turn = self._turns.get(session_id)
                if turn is not None and session_id not in self._loading:
                    turn.apply(params.get("update") or {})
            return
        if method == "session/request_permission":
            self._answer_permission(message["id"], params)
            return
        await self._reply(
            message["id"],
            error={"code": -32601, "message": f"Method not found: {method}"},
        )

    def _answer_permission(self, request_id: Any, params: dict[str, Any]) -> None:
        session_id = str(params.get("sessionId", ""))
        if self.on_permission is None:
            self._spawn(self._reply(request_id, result=_reject_option(params)))
            return
        handler = asyncio.ensure_future(self.on_permission(session_id, params))
        tasks = self._permission_tasks.setdefault(session_id, set())
        tasks.add(handler)

        async def answer() -> None:
            # Cancelling the handler, never this task, yields the cancelled outcome.
            try:
                result = await handler
            except asyncio.CancelledError:
                result = _CANCELLED
            except Exception:
                logger.exception("ACP permission handler failed")
                result = _CANCELLED
            finally:
                tasks.discard(handler)
                if not tasks:
                    self._permission_tasks.pop(session_id, None)
            await self._reply(request_id, result=result)

        self._spawn(answer())

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _reply(
        self,
        request_id: Any,
        *,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        body = {"error": error} if error is not None else {"result": result}
        with contextlib.suppress(AcpError):
            await self._send({"id": request_id, **body})
