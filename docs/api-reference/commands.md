# Command Tools API Reference

The Command tools category provides sophisticated workflow automation through command chains for ZulipChat MCP. These tools enable sequential command execution with shared context, conditional branching, and complex multi-step operations.

## Workflow Automation

### `execute_chain`

Execute sophisticated command chains for workflow automation.

**Parameters:**
- `commands` (list[dict]): List of command specifications

**Command Specification Format:**
```python
{
    "type": "command_type",
    "params": {
        # Command-specific parameters
    }
}
```

**Returns:**
```python
{
    "status": "success",
    "summary": {
        "executed": 3,
        "successful": 3,
        "failed": 0,
        "total_time": "0.245s",
        "commands": [
            {
                "name": "send_message",
                "status": "success",
                "execution_time": "0.123s"
            }
        ]
    },
    "context": {
        "key": "value",  # Final context state
        "search_results": [...],
        "response": "user_input"
    }
}
```

**Description:**
Supports sequential command execution with shared context, includes 4 command types (send_message, wait_for_response, search_messages, conditional_action), provides conditional branching with Python expressions, maintains execution context across commands, integrates with v0.4 tools (advanced_search adapter), handles async operations with fallback loops, and returns comprehensive execution summary with final context. Ideal for complex multi-step workflows like interactive conversations, data processing pipelines, and automated response systems.

**Example:**
```python
# Complex workflow with conditional logic
commands = [
    {
        "type": "search_messages",
        "params": {
            "query_key": "search_query"
        }
    },
    {
        "type": "conditional_action",
        "params": {
            "condition": "len(context.get('search_results', [])) > 0",
            "true_action": {
                "type": "send_message",
                "params": {
                    "to_key": "target_stream",
                    "content_template": "Found {count} messages",
                    "message_type": "stream"
                }
            },
            "false_action": {
                "type": "send_message",
                "params": {
                    "to_key": "target_stream",
                    "content": "No messages found",
                    "message_type": "stream"
                }
            }
        }
    }
]

result = execute_chain(commands)
```

---

### `list_command_types`

List all available command types for workflow construction.

**Parameters:** None

**Returns:**
```python
[
    "send_message",
    "wait_for_response",
    "search_messages",
    "conditional_action"
]
```

**Description:**
Returns supported command types array including send_message (Zulip messaging), wait_for_response (user input polling), search_messages (message query with v0.4 integration), and conditional_action (branching logic with Python expressions). Essential reference for building command chains with execute_chain. Each command type supports specific parameters and context integration for sophisticated workflow automation and multi-step operations.

---

## Command Types

### 1. `send_message`

Send messages through Zulip API with context templating.

**Parameters:**
- `to_key` (str): Context key for recipient (stream name or user emails)
- `content` (str, optional): Static message content
- `content_template` (str, optional): Template with context variables
- `content_key` (str, optional): Context key containing content
- `message_type` (str): "stream" or "private"
- `topic` (str, optional): Topic for stream messages
- `topic_key` (str, optional): Context key for topic

**Context Variables:**
The command can access context data in templates using `{variable_name}` syntax.

**Example:**
```python
{
    "type": "send_message",
    "params": {
        "to_key": "target_stream",
        "content_template": "Processing {item_count} items",
        "message_type": "stream",
        "topic": "Automation Status"
    }
}
```

---

### 2. `wait_for_response`

Wait for user response through agent communication system.

**Parameters:**
- `request_id_key` (str): Context key containing request ID (default: "request_id")

**Context Requirements:**
- Must have `request_id` in context from previous `request_user_input` call

**Context Updates:**
- Sets `response` key with user's response

**Example:**
```python
{
    "type": "wait_for_response",
    "params": {
        "request_id_key": "user_request_id"
    }
}
```

---

### 3. `search_messages`

Search messages with v0.4 advanced_search integration.

**Parameters:**
- `query_key` (str): Context key containing search query (default: "search_query")

**Context Requirements:**
- Must have search query string in context

**Context Updates:**
- Sets `search_results` key with message list

**Integration:**
Uses v0.4 `advanced_search` tool with backward compatibility mapping for legacy command chains.

**Example:**
```python
{
    "type": "search_messages",
    "params": {
        "query_key": "user_query"
    }
}
```

---

### 4. `conditional_action`

Conditional execution based on Python expressions.

**Parameters:**
- `condition` (str): Python expression evaluated against context
- `true_action` (dict): Command to execute if condition is true
- `false_action` (dict, optional): Command to execute if condition is false

**Condition Context:**
- Access context data via `context` variable
- No builtins available for security
- Example: `context.get('message_count', 0) > 5`

**Example:**
```python
{
    "type": "conditional_action",
    "params": {
        "condition": "context.get('user_confirmed') == 'yes'",
        "true_action": {
            "type": "send_message",
            "params": {
                "content": "Proceeding with action",
                "to_key": "notification_stream",
                "message_type": "stream"
            }
        },
        "false_action": {
            "type": "send_message",
            "params": {
                "content": "Action cancelled",
                "to_key": "notification_stream",
                "message_type": "stream"
            }
        }
    }
}
```

---

## Advanced Usage Patterns

### Interactive Workflow

```python
# Multi-step interactive workflow
workflow = [
    # Step 1: Send initial message
    {
        "type": "send_message",
        "params": {
            "to_key": "user_stream",
            "content": "Starting automated process. Do you want to continue?",
            "message_type": "stream",
            "topic": "Process Automation"
        }
    },

    # Step 2: Wait for confirmation (requires agent_message integration)
    {
        "type": "wait_for_response",
        "params": {
            "request_id_key": "confirmation_request"
        }
    },

    # Step 3: Conditional processing based on response
    {
        "type": "conditional_action",
        "params": {
            "condition": "context.get('response', '').lower() in ['yes', 'y', 'continue']",
            "true_action": {
                "type": "search_messages",
                "params": {
                    "query_key": "process_query"
                }
            },
            "false_action": {
                "type": "send_message",
                "params": {
                    "content": "Process cancelled by user",
                    "to_key": "user_stream",
                    "message_type": "stream"
                }
            }
        }
    },

    # Step 4: Report results
    {
        "type": "send_message",
        "params": {
            "content_template": "Process completed. Found {result_count} items.",
            "to_key": "user_stream",
            "message_type": "stream"
        }
    }
]

# Execute with initial context
initial_context = {
    "user_stream": "general",
    "process_query": "sender:bot@example.com",
    "confirmation_request": "req_12345"
}

result = execute_chain(workflow)
```

### Data Processing Pipeline

```python
# Automated data processing chain
pipeline = [
    # Search for recent data
    {
        "type": "search_messages",
        "params": {
            "query_key": "data_query"
        }
    },

    # Check if data was found
    {
        "type": "conditional_action",
        "params": {
            "condition": "len(context.get('search_results', [])) > 0",
            "true_action": {
                "type": "send_message",
                "params": {
                    "content_template": "Processing {count} data points...",
                    "to_key": "status_stream",
                    "message_type": "stream"
                }
            },
            "false_action": {
                "type": "send_message",
                "params": {
                    "content": "No data found to process",
                    "to_key": "status_stream",
                    "message_type": "stream"
                }
            }
        }
    }
]
```

### Error Handling Chain

```python
# Chain with error recovery
error_handling_chain = [
    {
        "type": "search_messages",
        "params": {
            "query_key": "primary_query"
        }
    },

    # Fallback search if no results
    {
        "type": "conditional_action",
        "params": {
            "condition": "len(context.get('search_results', [])) == 0",
            "true_action": {
                "type": "search_messages",
                "params": {
                    "query_key": "fallback_query"
                }
            }
        }
    },

    # Final status report
    {
        "type": "send_message",
        "params": {
            "content_template": "Search completed with {total} results",
            "to_key": "notification_channel",
            "message_type": "stream"
        }
    }
]
```

## Context Management

### Context Data Flow

The execution context flows between commands and provides:

1. **Shared State**: All commands can read/write to shared context
2. **Template Variables**: String templates can reference context values
3. **Conditional Logic**: Python expressions can evaluate context state
4. **Result Propagation**: Command outputs become available to subsequent commands

### Context Keys

Common context keys used by command types:

- `search_results`: Array of messages from search_messages
- `response`: User response from wait_for_response
- `message_id`: ID of sent message from send_message
- `request_id`: Request ID for user input operations
- Custom keys: Any application-specific data

### Template Syntax

String templates support Python format syntax:
- `{variable_name}` - Simple variable substitution
- `{count}` - Context value named 'count'
- `{search_results|length}` - Pipe filters (limited support)

## Error Handling

### Command-Level Errors

Individual command failures are captured in the execution summary:

```python
{
    "status": "partial_success",
    "summary": {
        "executed": 3,
        "successful": 2,
        "failed": 1,
        "commands": [
            {
                "name": "send_message",
                "status": "failed",
                "error": "Stream not found",
                "execution_time": "0.05s"
            }
        ]
    },
    "context": {
        # Final context despite failures
    }
}
```

### Chain-Level Errors

Critical failures that stop chain execution:

```python
{
    "status": "error",
    "error": "Invalid command specification",
    "executed_commands": ["search_messages"],
    "context": {
        # Context up to failure point
    }
}
```

## Integration with Agent Tools

Command chains integrate seamlessly with agent tools:

1. **Agent Communication**: Use `agent_message` to create request IDs for `wait_for_response`
2. **Task Tracking**: Wrap chains in `start_task`/`complete_task` calls
3. **Status Updates**: Send progress via `send_agent_status`
4. **AFK Mode**: Chains respect AFK mode settings

## Performance Considerations

- **Async Execution**: Commands run asynchronously with fallback loops
- **Context Size**: Large context data may impact performance
- **Chain Length**: Longer chains increase total execution time
- **API Rate Limits**: Multiple Zulip API calls may hit rate limits

## Security Notes

- **Expression Evaluation**: Conditional expressions run with restricted builtins
- **Context Access**: Commands can read all context data
- **Template Injection**: Avoid user-controlled template strings
- **API Permissions**: Commands use configured Zulip credentials

## Best Practices

1. **Start Simple**: Begin with basic command types before complex conditionals
2. **Context Planning**: Design context keys consistently across workflow
3. **Error Handling**: Include conditional actions for error scenarios
4. **Testing**: Test chains with various context states
5. **Documentation**: Comment complex conditional expressions
6. **Monitoring**: Use execution summaries for workflow analytics