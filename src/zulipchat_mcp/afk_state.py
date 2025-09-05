"""Simple AFK state management using JSON file storage."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class AFKState:
    """Manages AFK (Away From Keyboard) state for agent notifications."""

    def __init__(self):
        """Initialize AFK state manager."""
        self.state_file = Path.home() / ".claude" / "afk_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def _load_state(self) -> None:
        """Load state from file or create default."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    self.state = json.load(f)
            except (OSError, json.JSONDecodeError):
                self.state = self._default_state()
        else:
            self.state = self._default_state()

    def _default_state(self) -> dict[str, Any]:
        """Return default AFK state."""
        return {"afk": False, "since": None, "reason": None, "auto_return": None}

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except OSError:
            # Silently fail - AFK state is non-critical
            pass

    def is_afk(self) -> bool:
        """Check if currently AFK."""
        # Check for auto-return timeout
        if self.state["afk"] and self.state["auto_return"]:
            since = datetime.fromisoformat(self.state["since"])
            auto_return_time = since + timedelta(hours=self.state["auto_return"])
            if datetime.now() > auto_return_time:
                # Auto-deactivate
                self.deactivate()
                return False

        return self.state["afk"]

    def activate(
        self, reason: str | None = None, auto_hours: float | None = None
    ) -> dict[str, Any]:
        """Activate AFK mode."""
        self.state["afk"] = True
        self.state["since"] = datetime.now().isoformat()
        self.state["reason"] = reason or "Away from keyboard"
        self.state["auto_return"] = auto_hours
        self._save_state()

        return {
            "status": "success",
            "message": f"AFK mode activated: {self.state['reason']}",
            "auto_return_hours": auto_hours,
        }

    def deactivate(self) -> dict[str, Any]:
        """Deactivate AFK mode."""
        was_afk = self.state["afk"]
        self.state = self._default_state()
        self._save_state()

        return {
            "status": "success",
            "message": "AFK mode deactivated" if was_afk else "Already at keyboard",
            "was_afk": was_afk,
        }

    def toggle(
        self, reason: str | None = None, auto_hours: float | None = None
    ) -> dict[str, Any]:
        """Toggle AFK mode."""
        if self.is_afk():
            return self.deactivate()
        else:
            return self.activate(reason, auto_hours)

    def get_status(self) -> dict[str, Any]:
        """Get current AFK status."""
        status = {
            "afk": self.is_afk(),
            "since": self.state["since"],
            "reason": self.state["reason"],
            "auto_return": self.state["auto_return"],
        }

        if status["afk"] and status["since"]:
            # Calculate how long AFK
            since = datetime.fromisoformat(status["since"])
            duration = datetime.now() - since
            hours = duration.total_seconds() / 3600
            status["duration_hours"] = round(hours, 1)

            # Calculate time until auto-return
            if status["auto_return"]:
                remaining = status["auto_return"] - hours
                if remaining > 0:
                    status["auto_return_in"] = round(remaining, 1)

        return status


# Global instance for easy access
_afk_state = None


def get_afk_state() -> AFKState:
    """Get or create global AFK state instance."""
    global _afk_state
    if _afk_state is None:
        _afk_state = AFKState()
    return _afk_state
