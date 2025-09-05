# 🚀 ZulipChat MCP: Agent Communication System
## Enabling Claude Code ↔️ Human Communication via Zulip

### Vision Statement
Transform ZulipChat MCP into a bidirectional communication bridge between AI coding agents (like Claude Code) and developers, creating a seamless collaborative environment where agents can request input, report progress, and notify completion—all through Zulip's familiar chat interface.

---

## 🎯 Core Concept

**The Problem:** AI coding agents work in isolation. When they need clarification or complete tasks, there's no elegant way to communicate with the developer.

**The Solution:** Use Zulip as a real-time communication channel between Claude Code and humans, leveraging MCP tools to create a natural conversation flow.

```
Developer's Zulip ←→ ZulipChat MCP ←→ Claude Code
                          ↑
                   Agent Communication Layer
```

---

## 📋 Implementation Plan

### Phase 1: Foundation (Week 1)
**Goal:** Establish core agent registration and messaging infrastructure

#### 1.1 Agent Registration System
```python
@tool
def register_agent(
    agent_name: str,
    agent_type: str = "claude_code",
    private_stream: bool = True
) -> Dict[str, Any]:
    """
    Register an AI agent with dedicated Zulip communication channel
    
    Returns:
        {
            "agent_id": "uuid",
            "stream_name": "agent-claude-code",
            "bot_email": "claude-code-bot@domain.com",
            "webhook_url": "https://api/webhooks/agent/uuid"
        }
    """
```

#### 1.2 Dedicated Agent Streams
- Auto-create stream: `ai-agents/[agent_name]`
- Set up proper permissions (private by default)
- Create welcome message with agent capabilities
- Pin instructions for interacting with the agent

#### 1.3 Basic Message Flow
```python
@tool
def agent_message(
    agent_id: str,
    message_type: Literal["status", "question", "completion", "error"],
    content: str,
    metadata: Optional[Dict] = None
) -> MessageId:
    """
    Send a message from agent to human via Zulip
    """
```

### Phase 2: Interactive Communication (Week 2)
**Goal:** Enable two-way conversations and input requests

#### 2.1 Input Request System
```python
@tool
def request_user_input(
    agent_id: str,
    question: str,
    context: Dict[str, Any],
    options: Optional[List[str]] = None,
    timeout_seconds: int = 300
) -> UserResponse:
    """
    Agent requests input from user with context
    
    Example message in Zulip:
    🤖 Claude Code needs your input:
    
    Question: "Should I use PostgreSQL or SQLite for this project?"
    
    Context:
    - Project size: Small prototype
    - Expected users: < 100
    - Deployment: Local development
    
    Options:
    1️⃣ PostgreSQL
    2️⃣ SQLite
    3️⃣ Let me decide
    
    Reply with number or custom response...
    """
```

#### 2.2 Response Handling
```python
@tool
def wait_for_response(
    agent_id: str,
    request_id: str,
    timeout: int = 300
) -> Optional[str]:
    """
    Wait for user response to a specific request
    Returns None if timeout exceeded
    """
```

#### 2.3 Status Updates
```python
@tool
def send_agent_status(
    agent_id: str,
    status: Literal["working", "waiting", "blocked", "idle"],
    current_task: str,
    progress_percentage: Optional[int] = None,
    estimated_time: Optional[str] = None
) -> None:
    """
    Send live status updates to dedicated status topic
    """
```

### Phase 3: Task Management (Week 3)
**Goal:** Implement task tracking and completion notifications

#### 3.1 Task Lifecycle
```python
@tool
def start_task(
    agent_id: str,
    task_name: str,
    task_description: str,
    subtasks: Optional[List[str]] = None
) -> TaskId:
    """
    Notify user that agent is starting a new task
    Creates a new topic thread for this task
    """

@tool
def update_task_progress(
    task_id: TaskId,
    subtask_completed: Optional[str] = None,
    progress_percentage: Optional[int] = None,
    blockers: Optional[List[str]] = None
) -> None:
    """
    Update task progress in real-time
    """

@tool
def complete_task(
    task_id: TaskId,
    summary: str,
    outputs: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None
) -> None:
    """
    Mark task as complete with detailed summary
    
    Example completion message:
    ✅ Task Completed: "Implement user authentication"
    
    Summary:
    - Added JWT-based authentication
    - Created login/logout endpoints  
    - Added password hashing with bcrypt
    
    Files Modified:
    - src/auth/controller.py (127 lines added)
    - src/auth/middleware.py (89 lines added)
    - tests/test_auth.py (203 lines added)
    
    Tests: ✅ All passing (15 new tests)
    Coverage: 94% (+12%)
    Time taken: 12 minutes
    """
```

### Phase 4: Stream Organization (Week 4)
**Goal:** Implement stream management tools for better organization

#### 4.1 Stream Management
```python
@tool
def create_stream(
    name: str,
    description: str,
    is_private: bool = False,
    is_announcement_only: bool = False
) -> StreamId:
    """Create a new stream with configuration"""

@tool
def rename_stream(
    stream_id: StreamId,
    new_name: str
) -> bool:
    """Rename an existing stream"""

@tool
def archive_stream(
    stream_id: StreamId,
    message: Optional[str] = None
) -> bool:
    """Archive a stream with optional farewell message"""

@tool
def organize_streams_by_project(
    project_mapping: Dict[str, List[str]]
) -> Dict[str, List[StreamId]]:
    """
    Organize streams by project prefix
    Example: {"IOWarp": ["IOWarp-dev", "IOWarp-support"]}
    """
```

#### 4.2 Topic Management
```python
@tool
def get_stream_topics(
    stream_id: StreamId,
    include_archived: bool = False
) -> List[Topic]:
    """Get all topics in a stream"""

@tool
def move_topic(
    source_stream: StreamId,
    topic_name: str,
    dest_stream: StreamId
) -> bool:
    """Move a topic to another stream"""

@tool
def rename_topic(
    stream_id: StreamId,
    old_name: str,
    new_name: str
) -> bool:
    """Rename a topic within a stream"""
```

---

## 🏗️ Technical Architecture

### Backend Structure
```
zulipchat-mcp/
├── src/
│   ├── zulipchat_mcp/
│   │   ├── tools/
│   │   │   ├── agent_communication.py  # New: Agent tools
│   │   │   ├── stream_management.py    # New: Stream tools
│   │   │   ├── task_tracking.py        # New: Task tools
│   │   │   └── messaging.py            # Existing, enhanced
│   │   ├── models/
│   │   │   ├── agent.py               # Agent data models
│   │   │   └── task.py                # Task data models
│   │   └── services/
│   │       ├── agent_registry.py      # Agent management
│   │       └── webhook_handler.py     # Webhook processing
```

### Database Schema (SQLite)
```sql
-- Agent registry
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    stream_id INTEGER,
    bot_email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

-- Active tasks
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(id),
    name TEXT NOT NULL,
    description TEXT,
    status TEXT CHECK(status IN ('pending','active','completed','failed')),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    output_summary TEXT
);

-- Input requests
CREATE TABLE input_requests (
    id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(id),
    question TEXT NOT NULL,
    context JSON,
    response TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP
);
```

---

## 💻 Usage Examples

### Example 1: Claude Code Needs Clarification
```python
# In Claude Code's hook system
def on_ambiguous_request():
    response = mcp.request_user_input(
        agent_id="claude-code-001",
        question="Multiple test files found. Which should I run?",
        context={
            "files_found": ["test_unit.py", "test_integration.py", "test_e2e.py"],
            "user_request": "run the tests"
        },
        options=["All tests", "Unit tests only", "Integration tests only", "E2E tests only"]
    )
    return response.selection
```

**User sees in Zulip:**
```
🤖 Claude Code needs your input:

Question: Multiple test files found. Which should I run?

Found files:
• test_unit.py
• test_integration.py  
• test_e2e.py

Your request: "run the tests"

Reply with:
1️⃣ All tests
2️⃣ Unit tests only
3️⃣ Integration tests only
4️⃣ E2E tests only
```

### Example 2: Task Completion Notification
```python
# After Claude Code completes a feature
mcp.complete_task(
    task_id="task-789",
    summary="Successfully implemented dark mode toggle",
    outputs={
        "files_created": ["ThemeToggle.tsx", "theme.css"],
        "files_modified": ["App.tsx", "Settings.tsx"],
        "tests_added": 5,
        "test_status": "passing"
    },
    metrics={
        "lines_added": 245,
        "time_taken_minutes": 18,
        "test_coverage": "92%"
    }
)
```

**User sees in Zulip:**
```
✅ Task Completed: "Implement dark mode toggle"

Summary:
Successfully implemented dark mode toggle

📁 Files created:
• ThemeToggle.tsx
• theme.css

📝 Files modified:
• App.tsx
• Settings.tsx

🧪 Tests: 5 added, all passing
📊 Coverage: 92%
⏱️ Time: 18 minutes
```

### Example 3: Real-time Status Updates
```python
# Claude Code working on a complex refactor
mcp.send_agent_status(
    agent_id="claude-code-001",
    status="working",
    current_task="Refactoring authentication module",
    progress_percentage=45,
    estimated_time="~10 minutes remaining"
)
```

**User sees in status stream:**
```
🔄 Claude Code Status Update

Status: 🟢 Working
Task: Refactoring authentication module
Progress: ████████░░░░░░░░ 45%
ETA: ~10 minutes remaining
```

---

## 🚦 Implementation Timeline

### Week 1: Foundation
- [ ] Set up project structure
- [ ] Implement agent registration
- [ ] Create basic messaging tools
- [ ] Test with simple messages

### Week 2: Interactivity  
- [ ] Build input request system
- [ ] Implement response waiting
- [ ] Add timeout handling
- [ ] Create status update tools

### Week 3: Task Management
- [ ] Design task lifecycle
- [ ] Implement progress tracking
- [ ] Build completion notifications
- [ ] Add metrics collection

### Week 4: Organization
- [ ] Stream management tools
- [ ] Topic organization
- [ ] Bulk operations
- [ ] Polish and documentation

---

## 🔧 Configuration

### Environment Variables
```bash
# .env file
ZULIP_API_URL=https://your-org.zulipchat.com/api/v1
ZULIP_BOT_EMAIL=mcp-bot@your-org.zulipchat.com
ZULIP_BOT_API_KEY=your-bot-api-key

# Agent settings
DEFAULT_AGENT_STREAM_PREFIX=ai-agents
AGENT_MESSAGE_TIMEOUT=300
ENABLE_AGENT_WEBHOOKS=true

# Database
DATABASE_URL=sqlite:///zulipchat_agents.db
```

### Claude Code Integration
```yaml
# In Claude Code's config
hooks:
  on_task_start: |
    curl -X POST localhost:8080/mcp/agent/task/start \
      -d '{"task": "$TASK_NAME", "description": "$TASK_DESC"}'
  
  on_need_input: |
    curl -X POST localhost:8080/mcp/agent/request-input \
      -d '{"question": "$QUESTION", "context": "$CONTEXT"}'
  
  on_task_complete: |
    curl -X POST localhost:8080/mcp/agent/task/complete \
      -d '{"task_id": "$TASK_ID", "summary": "$SUMMARY"}'
```

---

## 🎉 Expected Outcomes

1. **Seamless Communication**: Claude Code can naturally communicate with developers through Zulip
2. **Better Visibility**: Real-time updates on what the agent is doing
3. **Reduced Friction**: No more guessing what the agent needs or checking if it's done
4. **Organized Workspace**: Streams automatically organized by project and purpose
5. **Historical Context**: All agent interactions logged and searchable in Zulip

---

## 🔮 Future Enhancements (Post-MVP)

- **Voice Notes**: Send voice messages to agent, get audio notifications
- **Code Reviews**: Agent requests code review before committing
- **Pair Programming**: Real-time collaborative coding sessions
- **Learning Mode**: Agent learns from user preferences and feedback
- **Multi-Agent Coordination**: Multiple agents working together with shared communication

---

## 📚 Resources

- [Zulip REST API Documentation](https://zulip.com/api/rest)
- [MCP SDK Documentation](https://github.com/anthropics/mcp)
- [Claude Code Hooks Documentation](https://docs.anthropic.com/claude-code/hooks)
- [Python Zulip API Client](https://github.com/zulip/python-zulip-api)

---

*This implementation plan transforms ZulipChat MCP from a simple messaging tool into a powerful agent communication platform, enabling the future of human-AI collaboration in software development.*