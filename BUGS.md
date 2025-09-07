# ZulipChat MCP - Known Issues & Bug Tracker

## Current Status: v2.3.0
**Overall Stability**: 91.7% success rate (22/24 tools working reliably)
**Production Ready**: Yes, with documented workarounds for known issues

---

## 🐛 **Active Bugs** (Need Fixes)

### **BUG-001: MCP Transport Hanging** 🔴 *Critical*
**Issue**: MCP stdio transport occasionally hangs during tool execution
**Symptoms**: 
- Tools appear to execute but never return results
- Server remains running but unresponsive to MCP calls
- No error messages in logs

**Reproduction**: 
1. Run MCP server with `uv run zulipchat-mcp`
2. Execute several MCP tool calls consecutively
3. Tools start hanging without output or errors

**Root Cause**: MCP stdio transport layer issue, not Zulip API problems
- ✅ Zulip API works fine (direct testing confirms)
- ❌ MCP protocol communication breaks down

**Workaround**: 
```bash
# Restart MCP connection in Claude Code
claude mcp remove zulipchat
claude mcp add zulipchat uv run zulipchat-mcp
```

**Impact**: High - affects all tool usage when it occurs
**Frequency**: Intermittent, often after extended use
**Priority**: High
**Assigned**: Not assigned
**Found**: 2025-09-07 during comprehensive testing session

---

### **BUG-002: Missing Credentials Silent Failure** 🟡 *Medium*
**Issue**: Server starts successfully even without Zulip credentials
**Symptoms**:
- MCP server appears to start normally
- All tools hang indefinitely when called
- No authentication error messages

**Reproduction**:
1. Clear all ZULIP_* environment variables
2. Start server with `uv run zulipchat-mcp` 
3. Server starts without validation
4. All MCP tools hang when executed

**Root Cause**: Server doesn't validate credentials at startup
**Expected Behavior**: Should fail fast with clear error message

**Workaround**: Ensure .env file loaded before server startup

**Impact**: Medium - confusing for setup/debugging
**Frequency**: Only during initial setup or credential issues
**Priority**: Medium (affects developer experience)
**Assigned**: Not assigned  
**Found**: 2025-09-07 during debugging session

---

### **BUG-003: User Interaction System Incomplete** 🟡 *Medium*
**Issue**: `request_user_input` and `wait_for_response` workflow broken
**Symptoms**:
- `request_user_input` ✅ sends questions successfully to Zulip
- `wait_for_response` ❌ polls database indefinitely
- No mechanism to process user responses from Zulip back to database

**Root Cause**: Missing message listener/webhook architecture
- Questions sent to Zulip ✅
- User responds in Zulip ✅  
- Response never updates database ❌

**Current State**:
```python
# This works
request_user_input(agent_id, "Should we proceed?")

# This hangs forever (no listener to update DB)
response = wait_for_response(request_id) 
```

**Impact**: Medium - interactive workflows unusable
**Frequency**: Always (architectural gap)
**Priority**: Medium (documented in v2.5.0 roadmap)
**Assigned**: Roadmap v2.5.0
**Found**: 2025-09-07 during comprehensive testing

---

## 🟢 **Minor Issues** (Workarounds Available)

### **ISSUE-001: Emoji Name Validation**
**Issue**: Some standard emoji names fail validation
**Example**: `white_check_mark` fails, `check` works
**Workaround**: Use shorter emoji names (`check`, `thumbs_up`, etc.)
**Impact**: Low - cosmetic issue with workaround
**Priority**: Low

### **ISSUE-002: Stream Creation Visibility Delay** 
**Issue**: Newly created streams don't appear immediately in `get_streams` results
**Cause**: Likely Zulip API caching behavior
**Workaround**: Wait 10-30 seconds or refresh stream list
**Impact**: Low - non-blocking, streams work correctly
**Priority**: Low

---

## 🔧 **Debugging Guidelines**

### **When MCP Tools Hang**:
1. **Check credentials**: Verify all ZULIP_* environment variables set
2. **Test direct API**: Run direct Zulip API test (see AGENTS.md)
3. **Restart MCP connection**: Remove and re-add in Claude Code
4. **Check server logs**: Look for authentication failures

### **Credential Validation Test**:
```bash
uv run python -c "
from src.zulipchat_mcp.config import ConfigManager
from src.zulipchat_mcp.core.client import ZulipClientWrapper
try:
    config = ConfigManager()
    client = ZulipClientWrapper(config)
    result = client.get_streams()
    print(f'✅ Working: {len(result.get('streams', []))} streams')
except Exception as e:
    print(f'❌ Failed: {e}')
"
```

### **MCP Server Health Check**:
```bash
# Check if server running
ps aux | grep zulipchat-mcp

# Kill hung server
pkill -f zulipchat-mcp

# Restart server
uv run zulipchat-mcp
```

---

## 📋 **Bug Report Template**

When reporting new bugs, please include:

```markdown
### **BUG-XXX: Brief Description** 🔴/🟡/🟢
**Issue**: Clear description of the problem
**Symptoms**: What you observe when bug occurs
**Reproduction Steps**: 
1. Step one
2. Step two  
3. Expected vs actual result

**Root Cause**: If known
**Workaround**: If available
**Impact**: High/Medium/Low + explanation
**Frequency**: Always/Often/Rarely + context
**Environment**: OS, Python version, uv version
**Found**: Date and context of discovery
```

---

## 📊 **Bug Statistics**

| Priority | Count | Status |
|----------|-------|--------|
| 🔴 Critical | 1 | Active (MCP transport hanging) |
| 🟡 Medium | 2 | 1 Active, 1 Roadmapped |
| 🟢 Low | 2 | Known with workarounds |
| **Total** | **5** | **Production Ready** |

**Bug Resolution Rate**: 0% (newly established tracking)
**Mean Time to Workaround**: < 5 minutes
**Mean Time to Fix**: TBD

---

## 🎯 **Fix Priority Order**
1. **BUG-001**: MCP transport hanging (critical user experience)
2. **BUG-002**: Credential validation (developer experience)
3. **BUG-003**: User interaction system (roadmap v2.5.0)
4. **ISSUE-001**: Emoji validation (cosmetic)
5. **ISSUE-002**: Stream visibility delay (Zulip-side issue)

---

*Last updated: 2025-09-07*
*Bug tracker established during comprehensive testing session*
*Next review: After implementing v2.4.0 scheduling features*