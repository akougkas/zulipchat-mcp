"""Service manager for background services like the Zulip message listener."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..services.message_listener import MessageListener
from ..utils.database_manager import DatabaseManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

_instance: ServiceManager | None = None
_instance_lock = threading.RLock()


class ServiceManager:
    """Manages background services for ZulipChat MCP."""

    def __init__(self, config_manager: ConfigManager, enable_listener: bool = False):
        self.config_manager = config_manager
        self.enable_listener = enable_listener
        self.listener_ref: dict[str, Any | None] = {"listener": None, "thread": None}
        self.client: ZulipClientWrapper | None = None
        self.dbm: DatabaseManager | None = None
        self._watcher_thread: threading.Thread | None = None
        self._started = False
        self._lock = threading.RLock()
        self._stopping = threading.Event()

    def start(self) -> None:
        """Start the service manager. Starts the listener lazily unless enabled."""
        with self._lock:
            if self._started:
                return
            try:
                self._stopping.clear()
                self.client = ZulipClientWrapper(
                    self.config_manager, use_bot_identity=True
                )
                self.dbm = DatabaseManager()
                self._started = True

                if self.enable_listener:
                    self._start_listener()
                    self._start_watcher()

                logger.info(
                    "Service manager started"
                    + (
                        " (listener enabled)"
                        if self.enable_listener
                        else " (listener off)"
                    )
                )
            except Exception as e:
                logger.error(f"Failed to start service manager: {e}")

    def _start_listener(self) -> None:
        """Start the message listener service."""
        with self._lock:
            if self._stopping.is_set():
                return
            listener_thread = self.listener_ref.get("thread")
            if (
                isinstance(listener_thread, threading.Thread)
                and listener_thread.is_alive()
            ):
                return

            if not self.client or not self.dbm:
                logger.error(
                    "Cannot start listener: client or database not initialized"
                )
                return

            listener = MessageListener(self.client, self.dbm)
            self.listener_ref["listener"] = listener

            def _run() -> None:
                try:
                    asyncio.run(listener.start())
                except Exception as e:
                    logger.error(f"Message listener exited with error: {e}")
                finally:
                    with self._lock:
                        if self.listener_ref.get("listener") is listener:
                            self.listener_ref["listener"] = None
                            self.listener_ref["thread"] = None

            t = threading.Thread(target=_run, name="zulip-listener", daemon=True)
            self.listener_ref["thread"] = t
            t.start()
            logger.info("Message listener started")

    def _start_watcher(self) -> None:
        """Start the listener supervisor thread if not already running."""
        with self._lock:
            if self._watcher_thread is not None and self._watcher_thread.is_alive():
                return
            self._watcher_thread = threading.Thread(
                target=self._listener_watcher, name="listener-watcher", daemon=True
            )
            self._watcher_thread.start()

    def _listener_watcher(self) -> None:
        """Restart the listener if it dies unexpectedly."""
        while not self._stopping.wait(5):
            try:
                listener_thread = self.listener_ref.get("thread")
                listener_alive = (
                    isinstance(listener_thread, threading.Thread)
                    and listener_thread.is_alive()
                )
                if self.enable_listener and not listener_alive:
                    self._start_listener()
            except Exception as e:
                logger.error(f"Listener watcher error: {e}")

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop listener services managed by this process."""
        with self._lock:
            if not self._started:
                return True
            self.enable_listener = False
            self._stopping.set()
            listener = self.listener_ref.get("listener")
            listener_thread = self.listener_ref.get("thread")
            watcher_thread = self._watcher_thread

        if isinstance(listener, MessageListener):
            listener.request_stop()

        if isinstance(listener_thread, threading.Thread):
            listener_thread.join(timeout=timeout)
            if listener_thread.is_alive():
                logger.warning("Message listener did not stop before timeout")
                return False

        if isinstance(watcher_thread, threading.Thread):
            watcher_thread.join(timeout=timeout)

        with self._lock:
            self.listener_ref["listener"] = None
            self.listener_ref["thread"] = None
            self._watcher_thread = None
            self.client = None
            self.dbm = None
            self._started = False
        logger.info("Service manager stopped")
        return True


def init_service_manager(
    config_manager: ConfigManager, enable_listener: bool = False
) -> ServiceManager:
    """Initialize the module-level ServiceManager singleton. Called by server.py."""
    global _instance
    with _instance_lock:
        if _instance is not None and not _instance.stop():
            raise RuntimeError("Previous Zulip listener is still stopping")
        _instance = ServiceManager(config_manager, enable_listener=enable_listener)
        return _instance


def ensure_listener() -> None:
    """Ensure the message listener is running. Lazy-starts ServiceManager if needed.

    Called by agent tools that depend on the background event stream
    (wait_for_response, poll_agent_events, teleport_chat with wait_for_reply).

    Each step is idempotent: start() no-ops if already started, _start_listener()
    no-ops if listener exists, _start_watcher() no-ops if thread is running.
    """
    global _instance

    with _instance_lock:
        if _instance is None:
            from ..config import get_config_manager

            _instance = ServiceManager(get_config_manager(), enable_listener=True)

        _instance.enable_listener = True
        _instance.start()
        _instance._start_listener()
        _instance._start_watcher()


def shutdown_service_manager() -> None:
    """Stop the module-level ServiceManager singleton."""
    global _instance
    with _instance_lock:
        if _instance is not None and _instance.stop():
            _instance = None
