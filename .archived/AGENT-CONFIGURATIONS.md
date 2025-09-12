# 🤖 Complete Agent Configuration Guide

## 🎯 **Universal Command Pattern**

ZulipChat MCP follows the exact same pattern as context7 across all AI agents:

```bash
uvx zulipchat-mcp --zulip-email YOUR_EMAIL --zulip-api-key YOUR_API_KEY --zulip-site YOUR_SITE
```

## 🔧 **Agent-Specific Configurations**

### **1. Claude Desktop**

**Location**: `~/.claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-email", "YOUR_EMAIL",
        "--zulip-api-key", "YOUR_API_KEY", 
        "--zulip-site", "YOUR_SITE"
      ]
    }
  }
}
```

**With Bot Identity** (Advanced):
```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-email", "YOUR_EMAIL",
        "--zulip-api-key", "YOUR_API_KEY",
        "--zulip-site", "YOUR_SITE",
        "--zulip-bot-email", "YOUR_BOT_EMAIL",
        "--zulip-bot-api-key", "YOUR_BOT_API_KEY"
      ]
    }
  }
}
```

---

### **2. Claude Code**

**Command Line**:
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

### **3. VS Code (with MCP Extension)**

**Location**: VS Code Settings → Extensions → MCP

```json
{
  "mcp.servers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-email", "YOUR_EMAIL",
        "--zulip-api-key", "YOUR_API_KEY",
        "--zulip-site", "YOUR_SITE"
      ],
      "type": "stdio"
    }
  }
}
```

---

### **4. Cursor**

**Location**: Cursor Settings → MCP Servers

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp", 
        "--zulip-email", "YOUR_EMAIL",
        "--zulip-api-key", "YOUR_API_KEY",
        "--zulip-site", "YOUR_SITE"
      ]
    }
  }
}
```

---

### **5. Gemini CLI**

**Location**: `~/.gemini/mcp_servers.json`

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-email", "YOUR_EMAIL", 
        "--zulip-api-key", "YOUR_API_KEY",
        "--zulip-site", "YOUR_SITE"
      ]
    }
  }
}
```

---

### **6. OpenCode**

**Location**: `~/.config/opencode/mcp.json`

```json
{
  "mcp": {
    "zulipchat": {
      "type": "local",
      "command": [
        "uvx", "zulipchat-mcp",
        "--zulip-email", "YOUR_EMAIL",
        "--zulip-api-key", "YOUR_API_KEY", 
        "--zulip-site", "YOUR_SITE"
      ],
      "enabled": true
    }
  }
}
```

---

### **7. Crush CLI**

**Location**: `~/.crush/mcp_config.json`

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-email", "YOUR_EMAIL",
        "--zulip-api-key", "YOUR_API_KEY",
        "--zulip-site", "YOUR_SITE"  
      ]
    }
  }
}
```

---

## 🚀 **Quick Setup Commands**

### **Generate All Configurations**:
```bash
./generate-configs.sh
```

### **Test Installation**:
```bash
uvx zulipchat-mcp --help
```

### **Test with Real Credentials**:
```bash
uvx zulipchat-mcp --zulip-email=test@example.com --zulip-api-key=test-key --zulip-site=https://test.zulipchat.com
```

## 🔍 **Verification Steps**

1. **Install ZulipChat MCP**: `uv tool install . --editable`
2. **Add to your AI agent** using the configuration above
3. **Restart your AI agent**
4. **Verify connection** shows "Connected" or similar status
5. **Test a tool**: Try asking your AI to send a Zulip message

## 🎯 **Context7 Comparison**

**Context7**:
```bash
npx -y @upstash/context7-mcp --api-key YOUR_API_KEY
```

**ZulipChat MCP** (identical pattern):
```bash
uvx zulipchat-mcp --zulip-email YOUR_EMAIL --zulip-api-key YOUR_API_KEY --zulip-site YOUR_SITE
```

Both follow the **exact same structure** across all AI agents - only the package manager (npx vs uvx) and arguments differ!

## 📋 **Available Tools**

Once connected, your AI agent has access to 19 comprehensive Zulip tools:

- **Messaging**: Send, edit, react, search messages
- **Streams**: Manage channels and subscriptions  
- **Agents**: Register AI agents with project context
- **Search**: Find messages, users, and generate summaries

Your AI can now interact with Zulip just like context7 interacts with documentation!