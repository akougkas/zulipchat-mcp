# 🌐 Universal Agent Compatibility - ZulipChat MCP

## 🎯 **Universal Command Pattern**

All AI agents use the same underlying CLI command. Only the configuration format differs:

```bash
uvx zulipchat-mcp --zulip-email YOUR_EMAIL --zulip-api-key YOUR_API_KEY --zulip-site YOUR_SITE
```

## 🤖 **Agent-Specific Configurations**

### **Claude Code** 
```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-email YOUR_EMAIL --zulip-api-key YOUR_API_KEY --zulip-site YOUR_SITE
```

**JSON Result**:
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp", "--zulip-email", "YOUR_EMAIL", "--zulip-api-key", "YOUR_API_KEY", "--zulip-site", "YOUR_SITE"]
    }
  }
}
```

---

### **OpenCode**
**Configuration**: `~/.config/opencode/mcp.json`
```json
{
  "mcp": {
    "zulipchat": {
      "type": "local",
      "command": ["uvx", "zulipchat-mcp", "--zulip-email", "YOUR_EMAIL", "--zulip-api-key", "YOUR_API_KEY", "--zulip-site", "YOUR_SITE"],
      "enabled": true
    }
  }
}
```

---

### **Gemini CLI**
**Configuration**: `~/.gemini/mcp_servers.json`
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp", "--zulip-email", "YOUR_EMAIL", "--zulip-api-key", "YOUR_API_KEY", "--zulip-site", "YOUR_SITE"]
    }
  }
}
```

---

### **Cursor**
**Configuration**: Add to Cursor settings
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": ["zulipchat-mcp", "--zulip-email", "YOUR_EMAIL", "--zulip-api-key", "YOUR_API_KEY", "--zulip-site", "YOUR_SITE"]
    }
  }
}
```

---

## 🚀 **Advanced Features (Optional)**

### **With Bot Identity** (All Agents)
Add these arguments for advanced dual-credential features:
```bash
--zulip-bot-email YOUR_BOT_EMAIL --zulip-bot-api-key YOUR_BOT_API_KEY
```

**Example - Claude Code with Bot**:
```bash
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-email YOUR_EMAIL \
  --zulip-api-key YOUR_API_KEY \
  --zulip-site YOUR_SITE \
  --zulip-bot-email YOUR_BOT_EMAIL \
  --zulip-bot-api-key YOUR_BOT_API_KEY
```

### **Debug Mode** (All Agents)
Add `--debug` for troubleshooting:
```bash
uvx zulipchat-mcp --debug --zulip-email ...
```

## ✅ **Verification Commands**

### **Test Installation**:
```bash
uvx zulipchat-mcp --help
```

### **Test with Credentials**:
```bash
uvx zulipchat-mcp --zulip-email=test@example.com --zulip-api-key=test-key --zulip-site=https://test.zulipchat.com --debug
```

## 🔧 **Key Benefits**

1. **Universal Compatibility**: Same command works across all AI agents
2. **Standard Pattern**: Follows same structure as context7, GitHub MCP, etc.
3. **Flexible Configuration**: CLI args or .env fallback for development
4. **Advanced Features**: Optional bot identity system
5. **Easy Debugging**: Built-in debug and help options

## 📋 **Quick Setup Checklist**

- [ ] Install: `uv tool install . --editable` (for development)
- [ ] Test: `uvx zulipchat-mcp --help`
- [ ] Configure: Use agent-specific format above
- [ ] Verify: Check agent shows "Connected" status
- [ ] Test Tools: Try MCP tools in your AI agent

**Result**: ZulipChat MCP works identically across Claude Code, OpenCode, Gemini CLI, Cursor, and any future MCP-compatible AI agent!