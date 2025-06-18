# Zulip API Keys Guide

This guide explains how to obtain and configure API keys for the ZulipChat MCP server.

## What You Need

To use the ZulipChat MCP server, you need three pieces of information:

1. **Zulip Site URL** - Your organization's Zulip URL (e.g., `https://your-org.zulipchat.com`)
2. **Email Address** - The email address associated with your Zulip account
3. **API Key** - A unique key that authenticates your requests

## Getting Your API Key

### Step 1: Access Your Zulip Organization

Navigate to your Zulip organization in your web browser. The URL typically looks like:
- `https://your-organization.zulipchat.com`
- `https://chat.your-company.com` (for custom domains)

### Step 2: Log In

Use your credentials to log into your Zulip account.

### Step 3: Navigate to Settings

1. Click on your **profile picture** or **avatar** in the top-right corner
2. Select **"Personal settings"** from the dropdown menu

### Step 4: Find API Key Section

1. In the settings page, click on the **"Account & privacy"** tab
2. Scroll down to find the **"API key"** section

### Step 5: Generate API Key

1. Click the **"Generate API key"** button
2. You may be prompted to enter your password for security
3. Your API key will be displayed - **copy it immediately**
4. **Important**: Store this key securely, as it won't be shown again

### Step 6: Note Your Email

Your email address is displayed in the same section. Make sure to note it down as you'll need it for configuration.

## API Key Security

### Best Practices

- **Never share your API key** with others
- **Don't commit API keys** to version control systems
- **Use environment variables** or secure configuration files
- **Regenerate keys regularly** for enhanced security
- **Revoke unused keys** immediately

### Secure Storage Options

#### Environment Variables (Recommended)
```bash
export ZULIP_EMAIL="your-bot@zulip.com"
export ZULIP_API_KEY="your-secret-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"
```

#### Configuration File
Create `~/.config/zulipchat-mcp/config.json`:
```json
{
  "email": "your-bot@zulip.com",
  "api_key": "your-secret-api-key",
  "site": "https://your-org.zulipchat.com"
}
```

#### Docker Secrets (Production)
```bash
echo "your-secret-api-key" | docker secret create zulip_api_key -
```

## Bot Users vs Personal Users

### Personal Account API Keys

- Use your personal account credentials
- Have the same permissions as your user account
- Suitable for personal automation and testing

### Bot Account API Keys (Recommended for Production)

Creating a dedicated bot account is recommended for production use:

1. **Create Bot Account**:
   - Go to your organization settings
   - Navigate to "Bots" section
   - Click "Add a new bot"
   - Choose "Generic bot" type
   - Set a name and username for your bot

2. **Configure Bot Permissions**:
   - Set appropriate stream subscriptions
   - Configure message sending permissions
   - Limit access to necessary streams only

3. **Get Bot Credentials**:
   - Copy the bot's email address
   - Copy the bot's API key
   - Use these instead of personal credentials

## Permissions and Access

### Required Permissions

The ZulipChat MCP server requires the following permissions:

- **Send messages** - To send messages to streams and users
- **Read messages** - To retrieve and search messages
- **Access streams** - To list and access stream information
- **Access users** - To get user directory information
- **Add reactions** - To add emoji reactions to messages
- **Edit messages** - To modify existing messages (if needed)

### Stream Access

Make sure your user/bot has access to the streams you want to interact with:

1. **Subscribe to streams** you want to monitor
2. **Ensure proper permissions** for private streams
3. **Test access** before deploying

## Testing Your API Key

### Quick Test

Use this command to test your API key:

```bash
curl -X GET \
  -u "your-email:your-api-key" \
  "https://your-org.zulipchat.com/api/v1/users/me"
```

### Using the MCP Server

Test with the Docker container:

```bash
docker run --rm \
  -e ZULIP_EMAIL="your-bot@zulip.com" \
  -e ZULIP_API_KEY="your-api-key" \
  -e ZULIP_SITE="https://your-org.zulipchat.com" \
  ghcr.io/akougkas/zulipchat-mcp:latest \
  python -c "from src.zulipchat_mcp.config import ConfigManager; print('✅ Valid' if ConfigManager().validate_config() else '❌ Invalid')"
```

## Troubleshooting

### Common Issues

**"Invalid API key" Error**
- Double-check the API key was copied correctly
- Ensure no extra spaces or characters
- Try regenerating the API key

**"Authentication failed" Error**
- Verify the email address is correct
- Check that the account is active
- Ensure the account has necessary permissions

**"Site not found" Error**
- Verify the site URL format: `https://your-org.zulipchat.com`
- Check for typos in the organization name
- Ensure the site is accessible from your network

### Getting Help

1. **Check Zulip Documentation**: [Zulip API Documentation](https://zulip.com/api/)
2. **Test with curl**: Use direct API calls to isolate issues
3. **Check permissions**: Ensure your account has necessary access
4. **Contact admin**: Your Zulip administrator can help with permissions

## API Key Rotation

For security, rotate your API keys regularly:

1. **Generate new API key** following the steps above
2. **Update configuration** with the new key
3. **Test the new key** thoroughly
4. **Revoke the old key** once confirmed working

## Multiple Organizations

If you use multiple Zulip organizations:

1. **Generate separate API keys** for each organization
2. **Use different configuration profiles** or environment variable sets
3. **Run separate MCP server instances** if needed

## Example Configurations

### Development Setup
```bash
# .env file
ZULIP_EMAIL="myname@company.zulipchat.com"
ZULIP_API_KEY="dev-api-key-here"
ZULIP_SITE="https://company.zulipchat.com"
MCP_DEBUG=true
```

### Production Setup
```bash
# Docker secrets or secure environment
ZULIP_EMAIL="chatbot@company.zulipchat.com"
ZULIP_API_KEY="prod-api-key-here"
ZULIP_SITE="https://company.zulipchat.com"
MCP_DEBUG=false
```

## Next Steps

Once you have your API key:

1. **Follow the [Setup Guide](setup-guide.md)** for installation
2. **Configure your MCP client** (Claude Desktop, etc.)
3. **Test the connection** with a simple message
4. **Explore the available tools** and features