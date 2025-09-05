# ZulipChat MCP - Claude Code Bot Identity Setup Guide

This guide will help you set up a dedicated Zulip bot for Claude Code to have its own identity when sending messages.

## Why Bot Identity?

Without bot credentials, all messages from Claude Code appear as coming from your user account. With a bot identity:
- Messages clearly show they're from "Claude Code" (AI Assistant)
- You can distinguish between human and AI messages
- The bot can have its own avatar and profile
- Better security separation

## Step 1: Create a Zulip Bot

1. **Navigate to Bot Settings**
   - Go to your Zulip instance: https://grc.zulipchat.com
   - Click the gear icon ⚙️ in the top-right
   - Select "Personal settings" → "Bots"
   - Or direct link: https://grc.zulipchat.com/#settings/your-bots

2. **Create New Bot**
   - Click "Add a new bot"
   - Fill in the bot details:
     - **Bot type**: Generic bot
     - **Full name**: Claude Code
     - **Username**: claude-code (or your preference)
     - **Bot avatar**: (optional) Upload an AI/robot icon

3. **Save Bot Credentials**
   - After creation, you'll see the bot's email and API key
   - **Bot email**: `claude-code-bot@grc.zulipchat.com`
   - **API key**: Click "show" and copy the key
   - Save these credentials securely

## Step 2: Configure MCP Server

### Option A: Environment Variables (Recommended)

Add to your `.env` file or shell configuration:

```bash
# User credentials (existing)
ZULIP_EMAIL="akougkas@iit.edu"
ZULIP_API_KEY="your-user-api-key"
ZULIP_SITE="https://grc.zulipchat.com"

# Bot credentials (new)
ZULIP_BOT_EMAIL="claude-code-bot@grc.zulipchat.com"
ZULIP_BOT_API_KEY="your-bot-api-key"
ZULIP_BOT_NAME="Claude Code"
ZULIP_BOT_AVATAR_URL="https://example.com/bot-avatar.png"  # Optional
```

### Option B: Configuration File

Create or update `~/.config/zulipchat-mcp/config.json`:

```json
{
  "email": "akougkas@iit.edu",
  "api_key": "your-user-api-key",
  "site": "https://grc.zulipchat.com",
  "bot_email": "claude-code-bot@grc.zulipchat.com",
  "bot_api_key": "your-bot-api-key",
  "bot_name": "Claude Code",
  "bot_avatar_url": "https://example.com/bot-avatar.png"
}
```

## Step 3: Test Bot Configuration

### Verify Bot Credentials

```bash
# Test bot configuration
uv run python -c "
from src.zulipchat_mcp.config import ConfigManager
from src.zulipchat_mcp.client import ZulipClientWrapper

config = ConfigManager()
print(f'User email: {config.config.email}')
print(f'Bot configured: {config.has_bot_credentials()}')
if config.has_bot_credentials():
    print(f'Bot email: {config.config.bot_email}')
    print(f'Bot name: {config.config.bot_name}')
    
    # Test bot client
    bot_client = ZulipClientWrapper(config, use_bot_identity=True)
    print(f'Bot identity active: {bot_client.identity == \"bot\"}')
    print(f'Bot display name: {bot_client.identity_name}')
"
```

### Send Test Message as Bot

```bash
# Test sending a message as the bot
uv run python -c "
from src.zulipchat_mcp.config import ConfigManager
from src.zulipchat_mcp.client import ZulipClientWrapper

config = ConfigManager()
bot_client = ZulipClientWrapper(config, use_bot_identity=True)

result = bot_client.send_message(
    message_type='stream',
    to='general',
    topic='Bot Test',
    content='🤖 Hello! This is Claude Code bot speaking.'
)
print(f'Message sent: {result.get(\"result\") == \"success\"}')
"
```

## Step 4: Register Claude Code Agent

When you use the MCP tools, Claude Code will automatically register itself as an agent:

```bash
# This happens automatically when you use agent tools
# But you can test it manually:
uv run python -c "
from src.zulipchat_mcp.server import register_agent
result = register_agent('Claude Code', 'claude_code', False)
if result.get('status') == 'success':
    print(f'Agent registered with ID: {result[\"agent\"][\"id\"]}')
    print(f'Stream created: {result[\"agent\"][\"stream_name\"]}')
"
```

## Step 5: Using Bot Identity in Claude Code

Once configured, Claude Code will automatically use the bot identity when:
1. Sending agent messages
2. Posting status updates
3. Requesting user input
4. Managing tasks

Messages will appear with clear attribution:
- **With bot**: "Claude Code (AI Assistant)"
- **Without bot**: "Claude Code (via MCP integration) - *Sent by: your-email*"

## Testing the Integration

### 1. Send a test message through MCP:

```python
# In Claude Code, you can test with:
import os
result = mcp__zulipchat__send_message(
    message_type="stream",
    to="general",
    content="Test from Claude Code",
    topic="Testing"
)
```

### 2. Register and use agent tools:

```python
# Register as an agent
result = mcp__zulipchat__register_agent(
    agent_name="Claude Code Test",
    agent_type="claude_code",
    private_stream=False
)
agent_id = result["agent"]["id"]

# Send agent message (will use bot identity)
mcp__zulipchat__agent_message(
    agent_id=agent_id,
    message_type="status",
    content="Claude Code is ready to assist!",
    metadata={"status": "online"}
)
```

## Troubleshooting

### Bot credentials not working?
1. Verify the bot exists in Zulip settings
2. Check API key hasn't been regenerated
3. Ensure bot has permissions to post to streams

### Messages still showing as user?
1. Check environment variables are loaded: `echo $ZULIP_BOT_EMAIL`
2. Restart the MCP server after configuration changes
3. Verify `config.has_bot_credentials()` returns `True`

### Permission errors?
1. Add bot to private streams manually
2. Check bot isn't deactivated in Zulip
3. Ensure API key has correct permissions

## Security Best Practices

1. **Never commit bot credentials** to version control
2. Use environment variables over config files when possible
3. Rotate bot API keys periodically
4. Limit bot permissions to necessary streams
5. Monitor bot activity in Zulip audit logs

## Advanced Features

### Custom Bot Avatar
Upload a custom avatar for your bot in Zulip settings to make it visually distinct.

### Stream Organization
The bot automatically creates streams like `ai-agents/claude-code` for organized communication.

### Status Indicators
Bot messages include visual indicators:
- 🟢 Working
- 🟡 Waiting
- 🔴 Blocked
- ⚪ Idle

## Support

If you encounter issues:
1. Check the logs: `uv run zulipchat-mcp --debug`
2. Verify configuration: `uv run python test_mcp_tools.py`
3. Open an issue: https://github.com/akougkas/zulipchat-mcp/issues