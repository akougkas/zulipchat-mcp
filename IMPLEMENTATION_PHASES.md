# ZulipChat MCP v2.0 - Complete Implementation Guide

## Mission Statement
Transform the overcomplicated ZulipChat MCP into a **lean, maintainable server** that enables bidirectional communication between AI agents and humans via Zulip. Remove 70% of complexity while keeping essential features.

## Context from Previous Session
- **Removed**: 5,000+ lines of overcomplicated code (database, async client, task tracking)
- **Simplified**: All agents use single "Agents-Channel" with structured topics
- **Key Learning**: MCP servers should be thin protocol layers, not complex applications
- **User Requirements**: Simple AFK mode, blocking wait for responses, project-local state

---

# PHASE 1: Foundation & Structure (2 hours)
*Goal: Create clean directory structure and split bloated server.py*

## Step 1.1: Initial Setup (15 min)
```bash
# Create new branch
git checkout -b feat/v2-simplification

# Create directory structure
mkdir -p src/zulipchat_mcp/{core,tools,utils,integrations}
mkdir -p examples/{claude_code,gemini,cursor}
mkdir -p .mcp  # Project-local state directory

# COMMIT: "feat: create v2 directory structure"
```

## Step 1.2: Move Core Files (30 min)
Move and organize existing files:
```
src/zulipchat_mcp/
├── core/
│   ├── cache.py         (move from root)
│   ├── exceptions.py    (move from root)
│   ├── security.py      (move from root)
│   └── agent_tracker.py (simplified version)
├── utils/
│   ├── logging.py       (rename from logging_config.py)
│   ├── metrics.py       (move from root)
│   └── health.py        (move from root)
```

**agent_tracker.py changes**:
- Remove global filesystem paths (~/.config)
- Use `.mcp/` in project directory
- Add runtime AFK flag (not persisted)

```bash
# COMMIT: "refactor: organize core modules into subdirectories"
```

## Step 1.3: Split server.py (45 min)
Current server.py is 1000+ lines. Split into:

**tools/messaging.py** (~200 lines):
```python
from mcp.server.fastmcp import FastMCP

def register_messaging_tools(mcp: FastMCP):
    @mcp.tool(description="Send a message to Zulip")
    def send_message(message_type: str, to: str, content: str, topic: str = None):
        # Move implementation from server.py
    
    @mcp.tool(description="Edit an existing message")
    def edit_message(message_id: int, content: str = None, topic: str = None):
        # Move implementation
    
    @mcp.tool(description="Add emoji reaction")
    def add_reaction(message_id: int, emoji_name: str):
        # Move implementation
```

**tools/streams.py** (~150 lines):
```python
def register_stream_tools(mcp: FastMCP):
    @mcp.tool(description="Get list of streams")
    def get_streams():
        # Move implementation
    
    @mcp.tool(description="Rename a stream")
    def rename_stream(stream_id: int, new_name: str):
        # Move implementation
    
    # Note: remove create_stream - agents shouldn't create streams
```

**tools/agents.py** (~250 lines):
```python
def register_agent_tools(mcp: FastMCP):
    @mcp.tool(description="""
    Register your agent session. ALWAYS call this first.
    Returns your topic in Agents-Channel.
    """)
    def register_agent(agent_type: str = "claude-code"):
        # Simplified: always use Agents-Channel
        # Topic: agent_type/YYYY-MM-DD/session_id
        # Save to .mcp/agent_registry.json
    
    @mcp.tool(description="""
    Send message to human. Only works when AFK is enabled.
    Set require_response=True to wait for input.
    """)
    def agent_message(content: str, require_response: bool = False):
        # Check runtime AFK flag
        # If require_response, generate response_id
        # Return immediately, let hook handle actual sending
    
    @mcp.tool(description="""
    Wait for human response. Blocks until received.
    """)
    def wait_for_response(response_id: str):
        # Poll .mcp/pending_responses.json
        # Block until response appears
        # No timeout
```

**server.py** (< 100 lines):
```python
from mcp.server.fastmcp import FastMCP
from .tools import messaging, streams, agents, search

mcp = FastMCP(
    "ZulipChat MCP",
    description="""
    Zulip integration for AI agents. Enables bidirectional communication.
    
    IMPORTANT FOR AGENTS:
    1. Always call register_agent() first
    2. Messages only send when user is AFK
    3. Use wait_for_response() for human input
    4. All messages go to "Agents-Channel" stream
    """
)

# Register all tool groups
messaging.register_messaging_tools(mcp)
streams.register_stream_tools(mcp)
agents.register_agent_tools(mcp)
search.register_search_tools(mcp)

if __name__ == "__main__":
    mcp.run()
```

```bash
# Test that server still starts
uv run python -m zulipchat_mcp.server

# COMMIT: "refactor: split server.py into modular tool groups"
```

## Step 1.4: Clean Up Imports (30 min)
- Fix all import paths
- Remove circular dependencies
- Update __init__.py files

```bash
# Run tests to verify nothing broke
uv run pytest tests/ -xvs

# COMMIT: "fix: update imports for new structure"
```

---

# PHASE 2: Agent Communication System (1.5 hours)
*Goal: Implement simplified agent-human communication*

## Step 2.1: Simplified Agent Tracker (30 min)
Create `core/agent_tracker.py`:
```python
import json
import uuid
from pathlib import Path
from datetime import datetime

class AgentTracker:
    """Minimal agent session tracker using project-local storage."""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.mcp_dir = Path.cwd() / ".mcp"
        self.mcp_dir.mkdir(exist_ok=True)
        
        # Runtime flag (not persisted)
        self.afk_enabled = False
    
    def register_agent(self, agent_type: str) -> dict:
        """Register agent and return topic assignment."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        topic = f"{agent_type}/{date_str}/{self.session_id}"
        
        # Save to registry
        registry_file = self.mcp_dir / "agent_registry.json"
        registry = json.loads(registry_file.read_text()) if registry_file.exists() else {"agents": []}
        registry["agents"].append({
            "agent_type": agent_type,
            "session_id": self.session_id,
            "topic": topic,
            "registered_at": datetime.now().isoformat()
        })
        registry_file.write_text(json.dumps(registry, indent=2))
        
        return {
            "stream": "Agents-Channel",
            "topic": topic,
            "session_id": self.session_id
        }
    
    def create_response_request(self, prompt: str) -> str:
        """Create a pending response entry."""
        response_id = str(uuid.uuid4())[:8]
        responses_file = self.mcp_dir / "pending_responses.json"
        
        responses = json.loads(responses_file.read_text()) if responses_file.exists() else {}
        responses[response_id] = {
            "prompt": prompt,
            "created_at": datetime.now().isoformat(),
            "response": None
        }
        responses_file.write_text(json.dumps(responses, indent=2))
        
        return response_id
    
    def check_response(self, response_id: str) -> str | None:
        """Check if response has been received."""
        responses_file = self.mcp_dir / "pending_responses.json"
        if not responses_file.exists():
            return None
        
        responses = json.loads(responses_file.read_text())
        if response_id in responses and responses[response_id]["response"]:
            return responses[response_id]["response"]
        return None
```

```bash
# COMMIT: "feat: implement minimal agent tracker with project-local state"
```

## Step 2.2: Hook Script for Message Handling (30 min)
Create `examples/hook_handler.py`:
```python
#!/usr/bin/env python3
"""
Hook handler for agent messages. This runs when agents send messages.
Checks AFK flag and sends to Zulip if enabled.
"""

import json
import sys
from pathlib import Path

def main():
    # Read message from stdin (from agent)
    message_data = json.loads(sys.stdin.read())
    
    # Check AFK flag in session state
    session_file = Path.cwd() / ".mcp" / "session_state.json"
    if not session_file.exists():
        print(json.dumps({"status": "skipped", "reason": "No session state"}))
        return
    
    session = json.loads(session_file.read_text())
    if not session.get("afk_enabled"):
        print(json.dumps({"status": "skipped", "reason": "AFK disabled"}))
        return
    
    # Send to Zulip using bot credentials
    # (Implementation depends on Zulip client setup)
    
    print(json.dumps({"status": "sent", "message_id": "12345"}))

if __name__ == "__main__":
    main()
```

```bash
# COMMIT: "feat: add hook handler for agent message routing"
```

## Step 2.3: Response Monitor (30 min)
Create `examples/response_monitor.py`:
```python
#!/usr/bin/env python3
"""
Monitors Agents-Channel for @response messages and updates pending_responses.json
"""

import json
import re
from pathlib import Path
from zulipchat_mcp.client import ZulipClientWrapper

def monitor_responses():
    client = ZulipClientWrapper()
    
    # Get recent messages from Agents-Channel
    messages = client.get_messages_from_stream("Agents-Channel", limit=50)
    
    for msg in messages:
        # Check for @response pattern
        match = re.search(r'@response\s+(\w+)\s+(.+)', msg.content)
        if match:
            response_id = match.group(1)
            response_text = match.group(2)
            
            # Update pending responses
            responses_file = Path.cwd() / ".mcp" / "pending_responses.json"
            if responses_file.exists():
                responses = json.loads(responses_file.read_text())
                if response_id in responses and not responses[response_id]["response"]:
                    responses[response_id]["response"] = response_text
                    responses_file.write_text(json.dumps(responses, indent=2))
                    print(f"Recorded response for {response_id}")

if __name__ == "__main__":
    monitor_responses()
```

```bash
# COMMIT: "feat: add response monitor for bidirectional communication"
```

---

# PHASE 3: Command Chains & Integration (1 hour)
*Goal: Expose command chains and integrate components*

## Step 3.1: Expose Command Chains (30 min)
Update `tools/commands.py`:
```python
from mcp.server.fastmcp import FastMCP
from ..commands import CommandChain, SendMessageCommand

def register_command_tools(mcp: FastMCP):
    @mcp.tool(description="""
    Execute a command chain for workflow automation.
    Example: Send multiple messages, wait for responses, take actions.
    """)
    def execute_chain(commands: list[dict]) -> dict:
        """Execute a sequence of commands."""
        chain = CommandChain()
        
        for cmd_data in commands:
            if cmd_data["type"] == "send_message":
                chain.add(SendMessageCommand(**cmd_data["params"]))
            # Add other command types
        
        result = chain.execute()
        return {"status": "success", "results": result}
    
    @mcp.tool(description="List available command types")
    def list_command_types() -> list[str]:
        return [
            "send_message",
            "wait_for_response", 
            "search_messages",
            "conditional_action"
        ]
```

```bash
# COMMIT: "feat: expose command chains as MCP tools"
```

## Step 3.2: AFK Command Handler (30 min)
Create `examples/afk_command.py`:
```python
#!/usr/bin/env python3
"""
Handle /zulipchat:afk slash command from Zulip.
Sets runtime flag in session_state.json
"""

import json
import sys
from pathlib import Path

def handle_afk(command: str):
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
    # Usage: python afk_command.py on|off|status
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    print(handle_afk(command))
```

```bash
# COMMIT: "feat: add AFK slash command handler"
```

---

# PHASE 4: Testing & Documentation (1 hour)
*Goal: Ensure everything works and document the system*

## Step 4.1: Integration Tests (30 min)
Create `tests/test_integration.py`:
```python
def test_agent_registration():
    """Test that agents can register and get assigned topics."""
    from zulipchat_mcp.tools.agents import register_agent
    
    result = register_agent("claude-code")
    assert result["stream"] == "Agents-Channel"
    assert "claude-code" in result["topic"]
    assert result["session_id"]

def test_message_with_response():
    """Test sending message and waiting for response."""
    from zulipchat_mcp.tools.agents import agent_message, wait_for_response
    
    # Send message requiring response
    msg = agent_message("Need approval to deploy", require_response=True)
    assert msg["response_id"]
    
    # Simulate user response
    responses_file = Path(".mcp/pending_responses.json")
    responses = json.loads(responses_file.read_text())
    responses[msg["response_id"]]["response"] = "approved"
    responses_file.write_text(json.dumps(responses))
    
    # Wait should return the response
    response = wait_for_response(msg["response_id"])
    assert response["response"] == "approved"

def test_afk_mode():
    """Test AFK mode affects message sending."""
    from zulipchat_mcp.core.agent_tracker import AgentTracker
    
    tracker = AgentTracker()
    
    # With AFK off, messages should be skipped
    tracker.afk_enabled = False
    # Test message sending...
    
    # With AFK on, messages should be sent
    tracker.afk_enabled = True
    # Test message sending...
```

```bash
# Run all tests
uv run pytest tests/ -xvs

# COMMIT: "test: add integration tests for agent communication"
```

## Step 4.2: Update Documentation (30 min)
Update `README.md`:
```markdown
# ZulipChat MCP v2.0

Lean MCP server for AI agent communication via Zulip.

## Key Features
- **Single Channel**: All agents use "Agents-Channel"
- **Structured Topics**: `agent_type/date/session_id`
- **Bidirectional**: Agents can wait for human responses
- **Simple AFK Mode**: Control when agents can send messages

## Quick Start
1. Install: `uvx --from git+https://github.com/user/zulipchat-mcp.git zulipchat-mcp`
2. Set credentials: `export ZULIP_EMAIL=... ZULIP_API_KEY=... ZULIP_SITE=...`
3. Register agent: `register_agent("claude-code")`
4. Enable AFK: `/zulipchat:afk on` in Zulip
5. Send messages: `agent_message("Task complete")`

## For AI Agents
Always:
1. Call `register_agent()` first
2. Check if human is AFK before sending
3. Use `wait_for_response()` when you need input
```

```bash
# COMMIT: "docs: update README for v2.0 architecture"
```

---

# PHASE 5: Cleanup & Optimization (30 min)
*Goal: Remove old code and optimize*

## Step 5.1: Remove Old Files
```bash
# Remove overcomplicated files
rm -rf src/zulipchat_mcp/database.py
rm -rf src/zulipchat_mcp/assistants.py
rm -rf src/zulipchat_mcp/async_client.py
rm -rf src/zulipchat_mcp/notifications.py
rm -rf src/zulipchat_mcp/models/
rm -rf agent_adapters/  # Move useful parts to examples/
rm -rf hooks/  # Move to examples/

# COMMIT: "cleanup: remove overcomplicated modules"
```

## Step 5.2: Final Testing
```bash
# Full test suite
uv run pytest tests/ --cov=src/zulipchat_mcp

# Test MCP server starts
uv run python -m zulipchat_mcp.server

# Test example usage
uv run python examples/test_flow.py

# COMMIT: "test: final testing and verification"
```

---

# Success Checklist

## Architecture Goals ✓
- [ ] No file > 500 lines
- [ ] server.py < 100 lines  
- [ ] Clear separation of concerns
- [ ] Project-local state (no global filesystem)

## Feature Goals ✓
- [ ] Single Agents-Channel
- [ ] Structured topics (type/date/session)
- [ ] Runtime AFK flag (not persisted)
- [ ] Blocking wait_for_response
- [ ] Command chains exposed

## Quality Goals ✓
- [ ] All tests passing
- [ ] No circular imports
- [ ] Clear documentation
- [ ] Example scripts for each client

## Final Result
A **lean, maintainable MCP server** that:
- Does one thing well (Zulip integration)
- Is easy to understand (30 min onboarding)
- Supports bidirectional agent communication
- Has minimal dependencies
- Uses simple file-based state

---

# Important Notes for Implementation

1. **Commit Often**: After each step, commit with clear message
2. **Test Continuously**: Run tests after each major change
3. **Keep It Simple**: Resist adding "nice to have" features
4. **Document As You Go**: Update docs with each phase
5. **Don't Over-Engineer**: If it feels complex, it probably is

Remember: This is about **removing complexity**, not adding features. The goal is a thin MCP protocol layer that enables agent-human communication via Zulip, nothing more.