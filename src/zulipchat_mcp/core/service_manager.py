"""Service manager for background services like message listener and AFK watcher."""

import asyncio
import threading
import time
from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..services.message_listener import MessageListener
from ..utils.database_manager import DatabaseManager
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ServiceManager:
    """Manages background services for ZulipChat MCP."""

    def __init__(self, config_manager: ConfigManager, enable_listener: bool = False):
        """Initialize service manager.

        Args:
            config_manager: Configuration manager instance
            enable_listener: Whether to enable message listener immediately
        """
        self.config_manager = config_manager
        self.enable_listener = enable_listener
        self.listener_ref: dict[str, Any | None] = {"listener": None, "thread": None}
        self.client: ZulipClientWrapper | None = None
        self.dbm: DatabaseManager | None = None
        self._watcher_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the service manager and AFK watcher."""
        try:
            # Initialize client and database manager
            self.client = ZulipClientWrapper(self.config_manager, use_bot_identity=True)
            self.dbm = DatabaseManager()

            # Start AFK watcher thread
            self._watcher_thread = threading.Thread(
                target=self._afk_watcher, name="afk-watcher", daemon=True
            )
            self._watcher_thread.start()
            logger.info("Service manager started")
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

    def _afk_watcher(self) -> None:
        """Monitor AFK state and manage listener accordingly."""
        # If CLI explicitly enabled, start immediately
        if self.enable_listener:
            self._start_listener()

        # Poll AFK state and toggle listener accordingly
        while True:
            try:
                if not self.dbm:
                    time.sleep(5)
                    continue

                state = self.dbm.get_afk_state() or {}
                enabled = bool(state.get("is_afk"))
                has_listener = self.listener_ref["listener"] is not None

                if enabled and not has_listener:
                    self._start_listener()
                elif (not enabled) and has_listener and not self.enable_listener:
                    self._stop_listener()
            except Exception as e:
                logger.error(f"AFK watcher error: {e}")
            time.sleep(5)
