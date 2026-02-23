# Commands API

Command-chain tools are extended mode only.

## Tools

- `execute_chain(commands, initial_context=None)`
- `list_command_types()`

## Supported command types

- `send_message`
- `wait_for_response`
- `search_messages`
- `conditional_action`

## Example

```python
await execute_chain(
    commands=[
        {
            "type": "search_messages",
            "params": {"query_key": "query"}
        },
        {
            "type": "conditional_action",
            "params": {
                "condition": "len(context.get('search_results', [])) > 0",
                "true_action": {
                    "type": "send_message",
                    "params": {
                        "message_type_key": "message_type",
                        "to_key": "to",
                        "content_key": "content",
                        "topic_key": "topic"
                    }
                }
            }
        }
    ],
    initial_context={
        "query": "deploy",
        "message_type": "stream",
        "to": "engineering",
        "topic": "deploy",
        "content": "Found matching messages"
    }
)
```

## Behavior notes

- Command chains run with shared context.
- `conditional_action` evaluates a Python expression against context.
- `search_messages` in chains adapts to current search tool behavior.
