# Agent Tools API Reference

The Agent tools category provides comprehensive agent lifecycle management, communication, and workflow automation capabilities for ZulipChat MCP. These tools enable AI agents to register, communicate with users, manage tasks, and coordinate operations through the Zulip platform.

## Agent Lifecycle Management

### `register_agent`

Register AI agent instance and create database records.

**Parameters:**
- `agent_type` (str, optional): Type of agent (default: "claude-code")

**Returns:**
```python
{
    "status": "success",
    "agent_id": "uuid4-string",
    "instance_id": "uuid4-string",
    "agent_type": "claude-code",
    "stream": "Agents-Channel",
    "afk_enabled": false,
    "warning": "Stream 'Agents-Channel' does not exist."  # if applicable
}
```

**Description:**
Essential first step for agent communication system. Generates unique agent_id and instance_id, stores agent metadata (type, session, project directory, hostname), initializes AFK state (disabled by default), validates Agents-Channel stream existence, and returns registration details. Creates persistent tracking across sessions with automatic UUID generation.

**Example:**
```python
# Register a new agent instance
result = register_agent(agent_type="claude-code")
agent_id = result["agent_id"]
```

---

### `list_instances`

Retrieve all agent instances with session details.

**Parameters:** None

**Returns:**
```python
{
    "status": "success",
    "instances": [
        {
            "instance_id": "uuid4-string",
            "agent_id": "uuid4-string",
            "agent_type": "claude-code",
            "session_id": "8-char-id",
            "project_dir": "/path/to/project",
            "host": "hostname",
            "started_at": "2024-01-01T12:00:00"
        }
    ]
}
```

**Description:**
Queries database for complete agent instance information, includes agent metadata (type, ID, session ID), project directory and hostname tracking, start timestamps and duration calculations, joins with agent records for full context, and returns sorted list (newest first). Essential for multi-agent coordination, session management, and system monitoring.

---

## Agent Communication

### `agent_message`

Send bot-authored messages to users via Agents-Channel stream using BOT identity.

**Parameters:**
- `content` (str): Message content to send
- `require_response` (bool, optional): Whether response is required (default: false)
- `agent_type` (str, optional): Agent type identifier (default: "claude-code")

**Returns:**
```python
{
    "status": "success",
    "message_id": 12345,
    "response_id": "8-char-id",  # if require_response=true
    "sent_via": "agent_message"
}
```

**Description:**
Formats agent messages with metadata, respects AFK mode gating (sends only when AFK enabled or ZULIP_DEV_NOTIFY=1), supports response requirements with unique IDs, automatically routes to Agents-Channel stream with contextual topics, and returns message ID for tracking. Use for automated responses, status updates, and agent-initiated communication. Bypassed when AFK disabled to prevent notification spam.

**Example:**
```python
# Send a status update
result = agent_message(
    content="Task completed successfully",
    require_response=False,
    agent_type="claude-code"
)
```

---

### `request_user_input`

Request interactive user input with intelligent routing.

**Parameters:**
- `agent_id` (str): Agent ID requesting input
- `question` (str): Question to ask user
- `options` (list[str], optional): Multiple choice options
- `context` (str, optional): Additional context information

**Returns:**
```python
{
    "status": "success",
    "request_id": "8-char-id",
    "message": "Input request sent"
}
```

**Description:**
Creates timestamped input requests with unique short IDs (8-char), supports multiple choice options and contextual information, respects AFK mode gating (only sends when enabled), routes via user email (DM), stream name, or fallback to Agents-Channel, stores requests in database for polling, and returns request ID for wait_for_response. Essential for agent-user interaction workflows.

**Example:**
```python
# Request user decision
result = request_user_input(
    agent_id="agent-123",
    question="Should I proceed with the deployment?",
    options=["Yes", "No", "Wait"],
    context="All tests have passed"
)
```

---

### `wait_for_response`

Wait for user response with timeout-based polling.

**Parameters:**
- `request_id` (str): Request ID from request_user_input

**Returns:**
```python
{
    "status": "success",
    "request_status": "answered",  # answered|cancelled|timeout
    "response": "Yes",
    "responded_at": "2024-01-01T12:05:00"
}
```

**Description:**
Monitors database for user replies to input requests, supports 5-minute timeout with 1-second polling intervals, handles request status tracking (answered/cancelled/timeout), returns response content with timestamps, and automatically updates request status on timeout. Use with request_user_input for interactive workflows. Blocks execution until response received or timeout reached.

---

## Task Management

### `start_task`

Initialize task tracking with database persistence.

**Parameters:**
- `agent_id` (str): Agent ID starting the task
- `name` (str): Task name
- `description` (str, optional): Task description

**Returns:**
```python
{
    "status": "success",
    "task_id": "uuid4-string"
}
```

**Description:**
Creates task records with unique IDs, stores task metadata (name, description, agent association), sets initial status and progress (0%), records start timestamps, and returns task_id for progress updates. Essential for long-running workflows and progress monitoring.

---

### `update_task_progress`

Update task progress with percentage and status tracking.

**Parameters:**
- `task_id` (str): Task ID to update
- `progress` (int): Progress percentage (0-100)
- `status` (str, optional): New status description

**Returns:**
```python
{
    "status": "success",
    "message": "Progress updated"
}
```

**Description:**
Modifies existing task records with new progress values (0-100%), supports optional status updates (working, blocked, error, etc.), updates database with current timestamp, and returns success confirmation. Use throughout task execution to provide progress visibility.

---

### `complete_task`

Finalize task completion with results tracking.

**Parameters:**
- `task_id` (str): Task ID to complete
- `outputs` (str, optional): Task outputs/results
- `metrics` (str, optional): Performance metrics

**Returns:**
```python
{
    "status": "success",
    "message": "Task completed"
}
```

**Description:**
Marks task as completed (100% progress), records completion timestamp, stores task outputs and performance metrics as text, updates database status to 'completed', and returns success confirmation. Final step in task lifecycle. Enables task analytics, outcome tracking, and results retrieval.

---

## Status Management

### `send_agent_status`

Set and track agent status updates.

**Parameters:**
- `agent_type` (str): Agent type identifier
- `status` (str): Status value (starting, working, completed, error, idle, etc.)
- `message` (str, optional): Additional status message

**Returns:**
```python
{
    "status": "success",
    "status_id": "uuid4-string"
}
```

**Description:**
Creates timestamped status records in database, supports custom agent types and status messages, generates unique status IDs for tracking, and stores operational state information. Use for progress reporting, health checks, and workflow state communication. Enables status history tracking across agent sessions.

---

## AFK Mode Management

### `enable_afk_mode`

Enable AFK (Away From Keyboard) mode for automatic notifications.

**Parameters:**
- `hours` (int, optional): Duration in hours (default: 8)
- `reason` (str, optional): Away reason message (default: "Away from computer")

**Returns:**
```python
{
    "status": "success",
    "message": "AFK mode enabled for 8 hours",
    "reason": "Away from computer"
}
```

**Description:**
Activates agent communication system with configurable duration, sets custom away reason message, stores AFK state in database with timestamps, enables agent_message and request_user_input tools to send notifications, and returns confirmation with duration. Use when away from computer to enable automatic agent communication.

---

### `disable_afk_mode`

Disable AFK mode and restore normal operation.

**Parameters:** None

**Returns:**
```python
{
    "status": "success",
    "message": "AFK mode disabled - normal operation"
}
```

**Description:**
Deactivates automatic agent notification system, updates database AFK state to disabled, blocks agent_message and request_user_input notifications (unless ZULIP_DEV_NOTIFY=1), sets reason to normal operation mode, and returns confirmation. Use when returning to computer to prevent notification spam.

---

### `get_afk_status`

Query current AFK mode status with state details.

**Parameters:** None

**Returns:**
```python
{
    "status": "success",
    "afk_state": {
        "enabled": false,
        "reason": "Normal operation",
        "updated_at": "2024-01-01T12:00:00"
    }
}
```

**Description:**
Retrieves AFK state from database, returns enabled/disabled status with reason message, includes last updated timestamp, normalizes boolean values for consistency, and provides current operational mode information. Use to check if automatic notifications are active before calling agent communication tools.

---

## Event Processing

### `poll_agent_events`

Poll unacknowledged chat events from Zulip with topic filtering.

**Parameters:**
- `limit` (int, optional): Maximum events to retrieve (default: 50)
- `topic_prefix` (str, optional): Topic filter prefix (default: "Agents/Chat/")

**Returns:**
```python
{
    "status": "success",
    "events": [
        {
            "id": "event-123",
            "message_id": 12345,
            "content": "User response here",
            "sender_email": "user@example.com",
            "topic": "Agents/Chat/Request-abc123",
            "timestamp": "2024-01-01T12:00:00"
        }
    ],
    "count": 1
}
```

**Description:**
Retrieves user messages and replies from Agents-Channel, filters by topic prefix, limits results, marks events as acknowledged in database, and returns event list with message content and metadata. Enables agent to receive user replies when in AFK mode. Essential for asynchronous agent-user communication and message queue processing.

---

## Usage Patterns

### Basic Agent Workflow

```python
# 1. Register agent
registration = register_agent(agent_type="claude-code")
agent_id = registration["agent_id"]

# 2. Start a task
task = start_task(agent_id, "Process user request")
task_id = task["task_id"]

# 3. Update progress
update_task_progress(task_id, 50, "Processing data")

# 4. Request user input if needed
input_request = request_user_input(
    agent_id,
    "Confirm action?",
    ["Yes", "No"]
)
response = wait_for_response(input_request["request_id"])

# 5. Complete task
complete_task(task_id, "Task completed successfully")
```

### AFK Mode Usage

```python
# Enable when going away
enable_afk_mode(hours=4, reason="In meeting")

# Agent messages will now be sent
agent_message("System maintenance starting")

# Disable when returning
disable_afk_mode()
```

## Identity Requirements

All agent tools require **BOT identity** for proper operation. The agent communication system is designed to work with bot credentials and routes messages through the designated Agents-Channel stream.

## Error Handling

All agent tools return consistent error responses:
```python
{
    "status": "error",
    "error": "Detailed error message"
}
```

Common error scenarios:
- Missing agent registration
- AFK mode restrictions
- Database connectivity issues
- Zulip API communication failures
- Missing bot credentials