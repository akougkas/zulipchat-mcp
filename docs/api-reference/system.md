# System Tools API Reference

The System tools category provides meta-functionality for server introspection, tool documentation, identity management, and bootstrap operations for ZulipChat MCP. These tools enhance client awareness, improve token efficiency, and provide operational guidance.

## Server Information

### `server_info`

Comprehensive server metadata and capabilities.

**Parameters:** None

**Returns:**
```python
{
    "name": "ZulipChat MCP",
    "version": "0.4.3",
    "features": ["tools"],
    "identities": {
        "available": ["user", "bot"],  # Available identity types
        "current": "user",             # Currently active identity
        "bot_supported": true          # Bot credentials configured
    },
    "docs": {
        "spec": "https://modelcontextprotocol.io/specification/2025-03-26",
        "fastmcp": "https://gofastmcp.com/getting-started/welcome"
    },
    "routing_hints": {
        "reads": "Use user identity for search/list/edit",
        "bot_replies": "Use agents.agent_message to reply in Agents-Channel",
        "send_message": "Use messaging.message for org streams (user identity)"
    },
    "limitations": [
        "File listing is limited by Zulip API; consider message parsing",
        "Analytics subscriber data depends on Zulip client API version"
    ]
}
```

**Description:**
Returns ZulipChat MCP server name/version, available identity types (user/bot/admin) with current selection, bot credential availability status, supported features list, routing hints for optimal tool selection, API limitations and workarounds, documentation links (MCP specification, FastMCP guides), and configuration status. Essential for understanding server capabilities, identity management, and optimal tool usage patterns. Use to check identity support before calling identity-specific tools.

**Example:**
```python
# Check server capabilities
info = server_info()
has_bot = info["identities"]["bot_supported"]
current_identity = info["identities"]["current"]
```

---

## Tool Documentation

### `tool_help`

On-demand detailed documentation for specific tools by name.

**Parameters:**
- `name` (str): Tool name to get documentation for

**Returns:**
```python
# Success case
{
    "tool": "send_message",
    "module": "src.zulipchat_mcp.tools.messaging_v25",
    "doc": "Send messages to Zulip streams or users with identity-aware routing...\n\nParameters:\n- to: Stream name or user emails..."
}

# Tool not found case
{
    "tool": "unknown_tool",
    "error": "Tool not found",
    "suggestions": ["send_message", "search_messages", "agent_message"]
}
```

**Description:**
Searches across all tool modules (messaging, streams, search, users, events, files, agents, commands), returns comprehensive docstrings with usage examples, provides module location and function details, suggests similar tools for typos/partial matches, and includes parameter descriptions and return values. Token-efficient approach - avoids bloating tool registry with verbose docs. Use when you need detailed implementation guidance for complex tools or parameter clarification.

**Example:**
```python
# Get detailed help for a specific tool
help_info = tool_help("agent_message")
documentation = help_info["doc"]

# Handle tool not found
help_info = tool_help("unknwn_tool")  # typo
if "suggestions" in help_info:
    print(f"Did you mean: {help_info['suggestions']}")
```

---

## Identity Management

### `identity_policy`

Identity management policy and best practices guide.

**Parameters:** None

**Returns:**
```python
{
    "policy": {
        "default": "user",
        "bot_usage": {
            "when": [
                "Send status or questions back to user via Agents-Channel (use agent_message)",
                "Schedule/draft messages when applicable"
            ],
            "where": "Agents-Channel (restricted)",
            "never_post": "Other org streams unless explicitly authorized"
        }
    },
    "recommended_channel": "Agents-Channel",
    "notes": [
        "Use agents.agent_message for bot-channel replies (no need for messaging.message)",
        "Ensure bot credentials are configured in .env",
        "User manages Zulip permissions to restrict bot to Agents-Channel"
    ]
}
```

**Description:**
Provides clear usage guidelines for USER/BOT/ADMIN identities, specifies when to use each identity type (USER for reads/edits, BOT for agent communication), defines bot usage restrictions (Agents-Channel only), includes security recommendations, explains permission boundaries, and provides routing hints for optimal identity selection. Essential for proper multi-identity tool usage and security compliance. Reference before switching identities or using bot features.

**Identity Usage Guidelines:**

#### User Identity (Default)
- **Purpose**: Interactive operations with standard permissions
- **Use for**: Reading, searching, editing operations
- **Scope**: Full organization access based on user permissions
- **Tools**: Most MCP tools default to user identity

#### Bot Identity
- **Purpose**: Automated operations with programmatic capabilities
- **Use for**: Agent communication, status updates, notifications
- **Scope**: Restricted to Agents-Channel for security
- **Tools**: `agent_message`, `register_agent`, agent communication tools

#### Security Model
- Bot permissions should be restricted in Zulip configuration
- User manages bot access through Zulip admin interface
- MCP server enforces channel restrictions in bot tools

---

## Bootstrap Operations

### `bootstrap_agent`

Bootstrap agent registration with bot identity validation.

**Parameters:**
- `agent_type` (str, optional): Type of agent to register (default: "claude-code")

**Returns:**
```python
{
    "status": "success",
    "agent_id": "uuid4-string",
    "instance_id": "uuid4-string",
    "agent_type": "claude-code",
    "stream": "Agents-Channel",
    "afk_enabled": false
}
```

**Description:**
Thin wrapper around agents.register_agent for early agent initialization, validates bot credentials availability, creates agent instance records in database, sets up Agents-Channel communication capability, and returns registration confirmation with IDs. Recommended first step for agent-based workflows. Encourages proper agent registration before using communication tools. Enables agent tracking and session management across the MCP server lifecycle.

**Example:**
```python
# Bootstrap a new agent session
result = bootstrap_agent(agent_type="claude-code")
if result["status"] == "success":
    agent_id = result["agent_id"]
    # Proceed with agent operations
```

---

## Usage Patterns

### Server Capability Discovery

```python
# Check server capabilities before operations
info = server_info()

# Verify identity support
if not info["identities"]["bot_supported"]:
    print("Bot features not available")

# Check current identity
current = info["identities"]["current"]
print(f"Operating as: {current}")

# Review routing hints
hints = info["routing_hints"]
print(f"For reads: {hints['reads']}")
```

### Identity Policy Guidance

```python
# Get identity usage guidance
policy = identity_policy()

# Check bot usage rules
bot_rules = policy["policy"]["bot_usage"]
print(f"Bot should be used when: {bot_rules['when']}")
print(f"Bot should post to: {bot_rules['where']}")
print(f"Bot should never post to: {bot_rules['never_post']}")

# Review setup notes
for note in policy["notes"]:
    print(f"Note: {note}")
```

### Tool Discovery and Help

```python
# Get help for specific tools
tools_to_check = ["agent_message", "send_message", "search_messages"]

for tool_name in tools_to_check:
    help_info = tool_help(tool_name)
    if "error" not in help_info:
        print(f"{tool_name}: {help_info['doc'][:100]}...")
    else:
        print(f"{tool_name}: Not found. Try: {help_info.get('suggestions', [])}")
```

### Complete Agent Bootstrap

```python
# Complete agent initialization workflow
def initialize_agent():
    # 1. Check server capabilities
    info = server_info()
    if not info["identities"]["bot_supported"]:
        return {"error": "Bot credentials not configured"}

    # 2. Review identity policy
    policy = identity_policy()
    print(f"Bot will use: {policy['recommended_channel']}")

    # 3. Bootstrap agent
    result = bootstrap_agent(agent_type="claude-code")
    if result["status"] != "success":
        return result

    # 4. Get tool help for key operations
    key_tools = ["agent_message", "request_user_input", "wait_for_response"]
    tool_docs = {}
    for tool in key_tools:
        help_info = tool_help(tool)
        if "error" not in help_info:
            tool_docs[tool] = help_info["doc"]

    return {
        "status": "ready",
        "agent_id": result["agent_id"],
        "server_info": info,
        "identity_policy": policy,
        "available_tools": tool_docs
    }

# Initialize complete agent environment
agent_env = initialize_agent()
```

## Integration with Other Tools

### Agent Tool Integration

System tools complement agent tools:

```python
# Check capabilities before agent registration
info = server_info()
if info["identities"]["bot_supported"]:
    # Use bootstrap_agent instead of direct register_agent
    result = bootstrap_agent()
    agent_id = result["agent_id"]
```

### Command Chain Integration

Use system tools in command chains for dynamic behavior:

```python
# Command chain that adapts to server capabilities
adaptive_chain = [
    {
        "type": "conditional_action",
        "params": {
            "condition": "context.get('server_info', {}).get('identities', {}).get('bot_supported')",
            "true_action": {
                "type": "send_message",
                "params": {
                    "content": "Bot features available",
                    "to_key": "status_channel",
                    "message_type": "stream"
                }
            },
            "false_action": {
                "type": "send_message",
                "params": {
                    "content": "Limited to user features",
                    "to_key": "status_channel",
                    "message_type": "stream"
                }
            }
        }
    }
]
```

## Error Handling

System tools return consistent error responses:

```python
{
    "status": "error",
    "error": "Detailed error message"
}
```

Common error scenarios:
- Tool not found in `tool_help`
- Missing bot credentials in `bootstrap_agent`
- Database connectivity issues
- Invalid agent type specifications

## Performance Considerations

- **Caching**: Server info results can be cached for session duration
- **Tool Help**: On-demand loading keeps memory usage efficient
- **Bootstrap**: One-time operation per agent session
- **Policy**: Static information, safe to cache

## Best Practices

1. **Capability Check**: Always check server capabilities before using advanced features
2. **Identity Awareness**: Review identity policy before switching identities
3. **Tool Discovery**: Use tool_help for unfamiliar tools instead of trial-and-error
4. **Bootstrap Pattern**: Use bootstrap_agent for consistent agent initialization
5. **Documentation**: Reference system tools in your workflow documentation
6. **Error Handling**: Handle missing capabilities gracefully in applications