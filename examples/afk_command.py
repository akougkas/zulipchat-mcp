#!/usr/bin/env python3
"""
Handle /zulipchat:afk command. Sets runtime flag in session_state.json
"""

import json
import sys
from pathlib import Path


def handle_afk(command: str) -> str:
    session_file = Path.cwd() / ".mcp" / "session_state.json"
    session_file.parent.mkdir(exist_ok=True)

    session = json.loads(session_file.read_text()) if session_file.exists() else {}

    if command == "on":
        session["afk_enabled"] = True
        message = "AFK mode enabled - agents can now send messages"
    elif command == "off":
        session["afk_enabled"] = False
        message = "AFK mode disabled - agent messages will be dropped"
    else:
        message = f"AFK status: {'enabled' if session.get('afk_enabled') else 'disabled'}"

    session_file.write_text(json.dumps(session, indent=2))
    return message


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    print(handle_afk(cmd))
