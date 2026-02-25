"""Service manager for background services like message listener and AFK watcher."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..services.message_listener import MessageListener
from ..utils.database_manager import DatabaseManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

_instance: ServiceManager | None = None


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

    def start(self) -> None:
        """Start the service manager. Only starts listener/AFK watcher if enabled."""
        if self._started:
            return
        try:
            self.client = ZulipClientWrapper(self.config_manager, use_bot_identity=True)
            self.dbm = DatabaseManager()
            self._started = True

            if self.enable_listener:
                self._start_listener()
                self._start_watcher()

            logger.info(
                "Service manager started"
                + (" (listener enabled)" if self.enable_listener else " (listener off)")
            )
        except Exception as e:
            logger.error(f"Failed to start service manager: {e}")

    def _start_listener(self) -> None:
        """Start the message listener service."""
        if self.listener_ref["listener"] is not None:
            return

        if not self.client or not self.dbm:
            logger.error("Cannot start listener: client or database not initialized")
            return

        listener = MessageListener(self.client, self.dbm)
        self.listener_ref["listener"] = listener

        def _run() -> None:
            asyncio.run(listener.start())

        t = threading.Thread(target=_run, name="zulip-listener", daemon=True)
        self.listener_ref["thread"] = t
        t.start()
        logger.info("Message listener started")

    def _stop_listener(self) -> None:
        """Stop the message listener service."""
        listener = self.listener_ref.get("listener")
        if listener is None:
            return

        try:
            asyncio.run(listener.stop())
        except Exception:
            pass

        self.listener_ref["listener"] = None
        self.listener_ref["thread"] = None
        logger.info("Message listener stopped")

    def _start_watcher(self) -> None:
        """Start the AFK watcher thread if not already running."""
        if self._watcher_thread is not None:
            return
        self._watcher_thread = threading.Thread(
            target=self._afk_watcher, name="afk-watcher", daemon=True
        )
        self._watcher_thread.start()

    def _afk_watcher(self) -> None:
        """Monitor AFK state and restart listener if it dies."""
        while True:
            try:
                if not self.dbm:
                    time.sleep(5)
                    continue

                state = self.dbm.get_afk_state() or {}
                is_afk = bool(state.get("is_afk"))
                auto_return_at = state.get("auto_return_at")

                if is_afk and auto_return_at is not None:
                    if isinstance(auto_return_at, datetime):
                        now = datetime.now(timezone.utc)
                        if auto_return_at.tzinfo is None:
                            auto_return_at = auto_return_at.replace(tzinfo=timezone.utc)
                        if now >= auto_return_at:
                            self.dbm.set_afk_state(
                                enabled=False, reason="Auto-returned from AFK"
                            )
                            logger.info("AFK auto-return triggered")

                if self.enable_listener and self.listener_ref["listener"] is None:
                    self._start_listener()
            except Exception as e:
                logger.error(f"AFK watcher error: {e}")
            time.sleep(5)


def init_service_manager(
    config_manager: ConfigManager, enable_listener: bool = False
) -> ServiceManager:
    """Initialize the module-level ServiceManager singleton. Called by server.py."""
    global _instance
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

    if _instance is None:
        from ..config import get_config_manager

        _instance = ServiceManager(get_config_manager(), enable_listener=True)

    _instance.enable_listener = True
    _instance.start()
    _instance._start_listener()
    _instance._start_watcher()
