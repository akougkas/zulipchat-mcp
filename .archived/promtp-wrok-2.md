# ZulipChat MCP v2.5.1 - Complete Missing Implementations

## Your Mission
Make all 24 MCP tools actually work. Currently they're registered but 4 have incomplete implementations. Fix the TODOs, create missing services, and ensure everything returns real data, not placeholders.

## Starting Point
```bash
# First, verify current state
uv sync
uv run python -m zulipchat_mcp.server --help  # Should show CLI args

# Check the specific TODOs
grep -n "TODO" src/zulipchat_mcp/tools/agents.py
# Line 143: wait_for_response - infinite loop
# Line 248: request_user_input - hardcoded to Agent-Channel
```

## Task 1: Create Message Listener Service (CRITICAL)

### File: `src/zulipchat_mcp/services/message_listener.py`

```python
"""Message listener service for processing Zulip events."""

import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.client import ZulipClientWrapper
from ..utils.database_manager import DatabaseManager  # You'll create this
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MessageListener:
    """Listens to Zulip event stream and processes responses."""
    
    def __init__(self, client: ZulipClientWrapper, db: DatabaseManager):
        self.client = client
        self.db = db
        self.running = False
        
    async def start(self):
        """Start listening to Zulip events."""
        self.running = True
        logger.info("Message listener started")
        
        while self.running:
            try:
                # Get events from Zulip
                # This is pseudo-code - adapt to actual Zulip API
                events = await self._get_events()
                
                for event in events:
                    if event['type'] == 'message':
                        await self._process_message(event['message'])
                        
            except Exception as e:
                logger.error(f"Listener error: {e}")
                await asyncio.sleep(5)  # Retry after error
    
    async def _process_message(self, message: dict):
        """Check if message is response to pending request."""
        # Get pending requests from database
        pending = self.db.get_pending_input_requests()
        
        for request in pending:
            if self._matches_request(message, request):
                # Update database with response
                self.db.update_input_request(
                    request['request_id'],
                    status='answered',
                    response=message['content'],
                    responded_at=datetime.now()
                )
                logger.info(f"Matched response for request {request['request_id']}")
                
    def _matches_request(self, message: dict, request: dict) -> bool:
        """Check if message matches request pattern."""
        # Implement matching logic:
        # - Check if from same user
        # - Check if in response thread
        # - Check for request ID in message
        # etc.
        pass
```

### Integration with wait_for_response

Update `src/zulipchat_mcp/tools/agents.py` line ~143:

```python
def wait_for_response(request_id: str) -> dict[str, Any]:
    """Wait for user response - now with actual listener."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "wait_for_response"}):
        track_tool_call("wait_for_response")
        try:
            db = DatabaseManager()  # Use new manager
            
            # Poll with timeout instead of infinite loop
            timeout = 300  # 5 minutes
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                result = db.get_input_request(request_id)
                
                if not result:
                    return {"status": "error", "error": "Request not found"}
                
                if result['status'] in ["answered", "cancelled"]:
                    return {
                        "status": "success",
                        "request_status": result['status'],
                        "response": result.get('response'),
                        "responded_at": result.get('responded_at')
                    }
                
                time.sleep(1)  # Poll every second
            
            # Timeout reached
            db.update_input_request(request_id, status='timeout')
            return {"status": "error", "error": "Response timeout"}
            
        except Exception as e:
            track_tool_error("wait_for_response", type(e).__name__)
            return {"status": "error", "error": str(e)}
```

## Task 2: Create DatabaseManager (HIGH PRIORITY)

### File: `src/zulipchat_mcp/utils/database_manager.py`

```python
"""Database manager for clean abstraction over DuckDB operations."""

import duckdb
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from ..utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages all database operations with proper abstraction."""
    
    def __init__(self, db_path: str = ".mcp/zulipchat/zulipchat.duckdb"):
        """Initialize database connection."""
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(db_path)
        logger.info(f"DatabaseManager connected to {db_path}")
    
    # Agent operations
    def create_agent_instance(self, agent_id: str, agent_type: str, 
                            project_name: str, **kwargs) -> dict:
        """Create new agent instance."""
        try:
            self.conn.execute("""
                INSERT INTO agent_instances 
                (agent_id, agent_type, project_name, machine_id, session_id, 
                 branch_name, created_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [agent_id, agent_type, project_name, kwargs.get('machine_id'),
                  kwargs.get('session_id'), kwargs.get('branch_name'),
                  datetime.now(), datetime.now()])
            return {"status": "success", "agent_id": agent_id}
        except Exception as e:
            logger.error(f"Failed to create agent instance: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_agent_instance(self, agent_id: str) -> Optional[dict]:
        """Get agent instance by ID."""
        result = self.conn.execute(
            "SELECT * FROM agent_instances WHERE agent_id = ?", 
            [agent_id]
        ).fetchone()
        
        if result:
            columns = [desc[0] for desc in self.conn.description]
            return dict(zip(columns, result))
        return None
    
    # User input requests
    def create_input_request(self, request_id: str, agent_id: str,
                           question: str, **kwargs) -> dict:
        """Create user input request."""
        try:
            self.conn.execute("""
                INSERT INTO user_input_requests
                (request_id, agent_id, question, options, context, 
                 status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """, [request_id, agent_id, question, kwargs.get('options'),
                  kwargs.get('context'), datetime.now()])
            return {"status": "success", "request_id": request_id}
        except Exception as e:
            logger.error(f"Failed to create input request: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_input_request(self, request_id: str) -> Optional[dict]:
        """Get input request by ID."""
        result = self.conn.execute(
            "SELECT * FROM user_input_requests WHERE request_id = ?",
            [request_id]
        ).fetchone()
        
        if result:
            columns = [desc[0] for desc in self.conn.description]
            return dict(zip(columns, result))
        return None
    
    def get_pending_input_requests(self) -> List[dict]:
        """Get all pending input requests."""
        results = self.conn.execute(
            "SELECT * FROM user_input_requests WHERE status = 'pending'"
        ).fetchall()
        
        if results:
            columns = [desc[0] for desc in self.conn.description]
            return [dict(zip(columns, row)) for row in results]
        return []
    
    def update_input_request(self, request_id: str, **updates) -> dict:
        """Update input request fields."""
        try:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [request_id]
            
            self.conn.execute(
                f"UPDATE user_input_requests SET {set_clause} WHERE request_id = ?",
                values
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to update input request: {e}")
            return {"status": "error", "error": str(e)}
    
    # Task operations
    def create_task(self, task_id: str, agent_id: str, name: str, **kwargs) -> dict:
        """Create new task."""
        # Implementation similar to above
        pass
    
    def update_task(self, task_id: str, **updates) -> dict:
        """Update task fields."""
        # Implementation similar to above
        pass
    
    # AFK state
    def get_afk_state(self) -> Optional[dict]:
        """Get current AFK state."""
        result = self.conn.execute(
            "SELECT * FROM afk_state ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        
        if result:
            columns = [desc[0] for desc in self.conn.description]
            return dict(zip(columns, result))
        return None
    
    def set_afk_state(self, enabled: bool, reason: str = "", hours: int = 0) -> dict:
        """Set AFK state."""
        try:
            # Clear existing state
            self.conn.execute("DELETE FROM afk_state")
            
            # Set new state
            self.conn.execute("""
                INSERT INTO afk_state (enabled, reason, hours, updated_at)
                VALUES (?, ?, ?, ?)
            """, [enabled, reason, hours, datetime.now()])
            
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to set AFK state: {e}")
            return {"status": "error", "error": str(e)}
```

## Task 3: Fix User Detection in request_user_input

### Update `src/zulipchat_mcp/tools/agents.py` line ~248:

```python
def request_user_input(
    agent_id: str,
    question: str,
    options: list[str] | None = None,
    context: str = "",
) -> dict[str, Any]:
    """Request input from user - now with smart routing."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "request_user_input"}):
        track_tool_call("request_user_input")
        try:
            db = DatabaseManager()  # Use new manager
            
            # Get agent instance to find associated user
            agent = db.get_agent_instance(agent_id)
            if not agent:
                return {"status": "error", "error": "Agent not found"}
            
            # Generate request ID
            request_id = str(uuid.uuid4())[:8]
            
            # Store in database
            db.create_input_request(
                request_id=request_id,
                agent_id=agent_id,
                question=question,
                options=json.dumps(options) if options else None,
                context=context
            )
            
            # Format message
            message = f"**Input Requested** (ID: {request_id})\n\n{question}"
            if options:
                message += "\n\nOptions:\n" + "\n".join(f"- {opt}" for opt in options)
            if context:
                message += f"\n\nContext: {context}"
            
            # Route based on agent metadata
            client = _get_client_bot()
            
            # Try to determine target from agent project/context
            if agent.get('user_email'):
                # Send DM to specific user
                result = client.send_message(
                    message_type="private",
                    to=[agent['user_email']],
                    content=message
                )
            elif agent.get('stream_name'):
                # Send to specific stream
                result = client.send_message(
                    message_type="stream",
                    to=agent['stream_name'],
                    content=message,
                    topic=f"Input-{agent['project_name']}-{request_id}"
                )
            else:
                # Fallback to Agent-Channel
                result = client.send_message(
                    message_type="stream",
                    to="Agent-Channel",
                    content=message,
                    topic=f"Input-{agent_id}-{request_id}"
                )
            
            if result.get("result") == "success":
                return {
                    "status": "success",
                    "request_id": request_id,
                    "message": "Input request sent"
                }
            
            return {"status": "error", "error": result.get("msg", "Failed to send")}
            
        except Exception as e:
            track_tool_error("request_user_input", type(e).__name__)
            return {"status": "error", "error": str(e)}
```

## Task 4: Complete Command Chain Implementation

### Update `src/zulipchat_mcp/tools/commands.py`:

```python
"""Command chain tools for workflow automation."""

from typing import Any, Dict, List
from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.commands.engine import CommandChain, Command
from ..utils.database_manager import DatabaseManager


class WaitForResponseCommand(Command):
    """Wait for user response command."""
    
    def execute(self, context: dict) -> dict:
        request_id = context.get('request_id')
        if not request_id:
            raise ValueError("request_id required in context")
        
        from ..tools.agents import wait_for_response
        result = wait_for_response(request_id)
        
        context['response'] = result.get('response')
        return context


class SearchMessagesCommand(Command):
    """Search messages command."""
    
    def execute(self, context: dict) -> dict:
        query = context.get('search_query')
        if not query:
            raise ValueError("search_query required in context")
        
        from ..tools.search import search_messages
        result = search_messages(query)
        
        context['search_results'] = result.get('messages', [])
        return context


class ConditionalActionCommand(Command):
    """Conditional execution based on context."""
    
    def __init__(self, condition: str, true_command: Command, false_command: Command = None):
        self.condition = condition
        self.true_command = true_command
        self.false_command = false_command
    
    def execute(self, context: dict) -> dict:
        # Evaluate condition (simple version - enhance as needed)
        condition_met = eval(self.condition, {"context": context})
        
        if condition_met:
            return self.true_command.execute(context)
        elif self.false_command:
            return self.false_command.execute(context)
        
        return context


def execute_chain(commands: list[dict]) -> dict:
    """Execute command chain with all command types."""
    chain = CommandChain("mcp_chain", client=ZulipClientWrapper(ConfigManager()))
    
    for cmd in commands:
        cmd_type = cmd.get("type")
        params = cmd.get("params", {})
        
        if cmd_type == "send_message":
            from ..core.commands.engine import SendMessageCommand
            chain.add_command(SendMessageCommand(**params))
            
        elif cmd_type == "wait_for_response":
            chain.add_command(WaitForResponseCommand())
            
        elif cmd_type == "search_messages":
            chain.add_command(SearchMessagesCommand())
            
        elif cmd_type == "conditional_action":
            # Build conditional command
            true_cmd = build_command(params.get("true_action"))
            false_cmd = build_command(params.get("false_action")) if params.get("false_action") else None
            chain.add_command(ConditionalActionCommand(
                params.get("condition"),
                true_cmd,
                false_cmd
            ))
    
    context = chain.execute(initial_context={})
    return {
        "status": "success",
        "summary": chain.get_execution_summary(),
        "context": context.data,
    }


def build_command(cmd_dict: dict) -> Command:
    """Helper to build command from dict."""
    # Implement based on command type
    pass


def list_command_types() -> list[str]:
    """List all available command types."""
    return [
        "send_message",
        "wait_for_response",
        "search_messages",
        "conditional_action",
    ]
```

## Task 5: Update All Database Calls

Search and replace all direct database access with DatabaseManager:

```bash
# Find all direct database usage
grep -r "get_database()" src/zulipchat_mcp/

# Replace with DatabaseManager pattern
# Example before:
db = get_database()
db.query_one(...)

# After:
db = DatabaseManager()
db.get_input_request(...)
```

## Verification Steps

After implementing each task, verify:

```bash
# 1. Test imports
uv run python -c "
from zulipchat_mcp.services.message_listener import MessageListener
from zulipchat_mcp.utils.database_manager import DatabaseManager
print('✓ New modules import successfully')
"

# 2. Test wait_for_response doesn't hang
uv run python -c "
from zulipchat_mcp.tools.agents import wait_for_response
# Should timeout after 5 minutes, not infinite
"

# 3. Test server starts
uv run python -m zulipchat_mcp.server \
  --zulip-email test@example.com \
  --zulip-api-key test-key \
  --zulip-site https://test.zulipchat.com

# 4. Format your code
uv run black src/zulipchat_mcp/

# 5. Check for remaining TODOs
grep -r "TODO\|FIXME\|XXX" src/zulipchat_mcp/
```

## Create Progress Report

### File: `IMPLEMENTATION-REPORT.md`

```markdown
# Implementation Report for ZulipChat MCP v2.5.1

## Completed Tasks

### 1. Message Listener Service
- Created: `src/zulipchat_mcp/services/message_listener.py`
- Purpose: Process Zulip events and update database for responses
- Integration: Connected to wait_for_response tool

### 2. DatabaseManager Pattern
- Created: `src/zulipchat_mcp/utils/database_manager.py`
- Methods: 15+ methods for all database operations
- Migration: Updated all tools to use manager instead of direct access

### 3. Fixed wait_for_response
- File: `src/zulipchat_mcp/tools/agents.py` (line 143)
- Change: Replaced infinite loop with timeout-based polling
- Result: No longer hangs, times out after 5 minutes

### 4. Fixed request_user_input
- File: `src/zulipchat_mcp/tools/agents.py` (line 248)
- Change: Added user detection from agent metadata
- Result: Routes to correct user/stream instead of always Agent-Channel

### 5. Command Chain Completion
- File: `src/zulipchat_mcp/tools/commands.py`
- Added: WaitForResponseCommand, SearchMessagesCommand, ConditionalActionCommand
- Result: Full workflow automation capability

## Verification Performed

```bash
# All imports work
✓ from zulipchat_mcp.services.message_listener import MessageListener
✓ from zulipchat_mcp.utils.database_manager import DatabaseManager

# Server starts without errors
✓ uv run python -m zulipchat_mcp.server --help

# No infinite loops
✓ wait_for_response has timeout
✓ request_user_input routes correctly
```

## Remaining Issues
- None found, all 24 tools now functional

## Test Commands Used
[List the actual commands you tested]
```

## Success Criteria Checklist

When you're done, ALL of these must be checked:
- [ ] Created `message_listener.py` with event processing
- [ ] Created `database_manager.py` with all DB methods
- [ ] Fixed `wait_for_response` - no infinite loop
- [ ] Fixed `request_user_input` - smart routing
- [ ] Added all command types to commands.py
- [ ] Replaced all direct DB access with manager
- [ ] Server starts without hanging
- [ ] All 24 tools return real data
- [ ] Created IMPLEMENTATION-REPORT.md

## Final Note
Focus on making things work, not perfect. The user wants functional code. Test that the server starts and tools can be called. Document what you did clearly so it can be reviewed.