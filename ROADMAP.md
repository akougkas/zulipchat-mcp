# ZulipChat MCP Roadmap

## Current Status: v2.3.0 (Production Ready)
- ✅ 22 MCP Tools operational (91.7% success rate)
- ✅ Clean v2.0 architecture with 59ms latency
- ✅ Professional bot identity system
- ✅ Comprehensive testing and documentation complete

---

## 📅 **Planned Features & Enhancements**

### **v2.4.0 - Message Scheduling** 🎯 *Next Priority*

**Goal**: Add message scheduling capabilities to MCP interface

**Current State**: 
- ✅ Scheduler service exists (`services/scheduler.py`) 
- ❌ Not exposed as MCP tool

**Implementation Plan**:
1. **Add MCP Tool Wrapper** 
   - Create `schedule_message` tool in `tools/messaging.py`
   - Expose native Zulip scheduling API through MCP interface
   - Support delayed message delivery (minutes, hours, days)

2. **Tool Specification**:
   ```python
   @mcp.tool(description="Schedule a message to be sent at a future time")
   def schedule_message(
       message_type: str,
       to: str, 
       content: str,
       scheduled_time: str,  # ISO format: "2025-01-01T12:00:00Z"
       topic: str | None = None
   ) -> dict[str, Any]
   ```

3. **Additional Scheduling Tools**:
   - `list_scheduled_messages` - View pending scheduled messages
   - `cancel_scheduled_message` - Cancel a scheduled message
   - `reschedule_message` - Modify scheduled message time/content

**Acceptance Criteria**:
- [ ] `mcp__zulipchat__schedule_message` tool available
- [ ] Supports standard datetime formats
- [ ] Integrates with existing Zulip scheduling API
- [ ] Proper error handling for invalid times/permissions
- [ ] Update tool count: 22 → 25 MCP tools

**Estimated Effort**: 2-3 hours
**Priority**: High (user-requested feature)

---

### **v2.5.0 - Enhanced User Interaction System**

**Goal**: Complete the user interaction workflow

**Current Issues**:
- ✅ `request_user_input` sends questions
- ❌ `wait_for_response` needs message listener architecture

**Implementation Plan**:
1. **Message Listener Service**
   - Webhook handler for incoming Zulip messages
   - Pattern matching for response IDs
   - Database updates when users respond

2. **Enhanced Response Processing**:
   - Support multiple response formats (text, numbered choices)
   - Timeout handling for unanswered requests
   - Response validation and parsing

**Estimated Effort**: 4-6 hours  
**Priority**: Medium (fixes incomplete feature)

---

### **v2.6.0 - Advanced Agent Management**

**Goal**: Enterprise-grade agent coordination

**Planned Features**:
- Agent-to-agent communication protocols
- Workflow orchestration between multiple agents
- Agent performance monitoring and metrics
- Multi-tenant agent isolation

**Estimated Effort**: 8-12 hours
**Priority**: Low (nice-to-have for advanced users)

---

### **v3.0.0 - MCP Standardization**

**Goal**: Align with industry MCP patterns

**Current Gap**: Uses .env configuration vs standard uvx patterns

**Implementation Plan**:
1. Remove DuckDB config storage (keep for app data only)
2. Simplify ConfigManager to environment-only approach
3. Fix pyproject.toml for proper uvx compatibility  
4. Implement standard `uvx zulipchat-mcp` → `claude mcp add zulipchat` flow

**Estimated Effort**: 6-8 hours
**Priority**: Medium (standardization important for adoption)

---

## 🤝 **Contributing**

### How to Add Items to Roadmap:
1. **Identify need** through user feedback or testing
2. **Research complexity** and existing code impact
3. **Add entry** with clear acceptance criteria
4. **Estimate effort** realistically  
5. **Prioritize** based on user value and technical complexity

### Priority Levels:
- **High**: User-requested, blocks workflows, or critical bugs
- **Medium**: Improves experience, fixes incomplete features
- **Low**: Nice-to-have enhancements, optimization

---

## 📊 **Version History**

| Version | Features | Tools | Status |
|---------|----------|-------|---------|
| v2.3.0 | Production testing, documentation | 22 | ✅ Released |
| v2.2.0 | Bot identity, v2.0 architecture | 22 | ✅ Released |
| v2.1.0 | Performance optimization (59ms) | 19 | ✅ Released |
| v2.0.0 | Complete architectural refactor | 19 | ✅ Released |

---

*Last updated: 2025-09-07 by Claude Code*
*Next review: When v2.4.0 scheduling feature is implemented*