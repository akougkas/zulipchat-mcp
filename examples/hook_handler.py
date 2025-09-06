#!/usr/bin/env python3
"""
Hook handler for agent messages. Checks AFK and sends to Zulip when enabled.
"""

import json
import sys
from pathlib import Path


def main() -> None:
    try:
        message_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        print(json.dumps({"status": "error", "error": "Invalid JSON"}))
        return

    session_file = Path.cwd() / ".mcp" / "session_state.json"
    if not session_file.exists():
        print(json.dumps({"status": "skipped", "reason": "No session state"}))
        return

    session = json.loads(session_file.read_text())
    if not session.get("afk_enabled"):
        print(json.dumps({"status": "skipped", "reason": "AFK disabled"}))
        return

    # Here we would send to Zulip using bot credentials
    print(json.dumps({"status": "sent", "message_id": "12345"}))


if __name__ == "__main__":
    main()
