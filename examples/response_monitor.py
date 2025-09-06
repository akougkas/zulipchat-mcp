#!/usr/bin/env python3
"""
Monitors Agents-Channel for @response messages and updates pending_responses.json
"""

import json
import re
from pathlib import Path

from zulipchat_mcp.client import ZulipClientWrapper
from zulipchat_mcp.config import ConfigManager


def monitor_responses() -> None:
    client = ZulipClientWrapper(ConfigManager())
    messages = client.get_messages_from_stream("Agents-Channel", limit=50)

    for msg in messages:
        match = re.search(r"@response\s+(\w+)\s+(.+)", msg.content)
        if match:
            response_id = match.group(1)
            response_text = match.group(2)

            responses_file = Path.cwd() / ".mcp" / "pending_responses.json"
            if responses_file.exists():
                responses = json.loads(responses_file.read_text())
            else:
                responses = {"pending": {}}

            if response_id in responses.get("pending", {}) and not responses["pending"][response_id].get("response"):
                responses["pending"][response_id]["response"] = response_text
                responses_file.parent.mkdir(exist_ok=True)
                responses_file.write_text(json.dumps(responses, indent=2))
                print(f"Recorded response for {response_id}")


if __name__ == "__main__":
    monitor_responses()
