# FIXES.md - Surgical Bug Fixes for v2.5.0

## Priority 1: Parameter Type Validation Issue

### Problem
Tools fail when called from Claude Code with: `'3' is not valid under any of the given schemas`
- FastMCP is passing strings but functions expect integers
- Only affects: `last_days`, `last_hours`, similar optional int parameters

### Investigation Needed
1. Check how FastMCP handles type conversion in `src/zulipchat_mcp/server.py`
2. Look at tool registration in `register_*_v25_tools` functions
3. Find where FastMCP generates schemas from function signatures

### Surgical Fix
- Find the exact point where MCP protocol meets our functions
- Add minimal type handling at that boundary layer ONLY
- Do NOT add type coercion to individual functions

## Priority 2: Empty Analytics Results

### Symptoms
- `analytics` and `get_daily_summary` return empty datasets
- Tools work but might have wrong time filters or data scope

### Quick Checks
1. Test with explicit time ranges that definitely have data
2. Check if narrow filters are too restrictive
3. Verify the Zulip client is getting any messages at all

## Priority 3: File Listing Limitation

### Current State
- `manage_files` list operation has API limitations
- Already returns helpful message about custom implementation

### Decision Needed
- Leave as-is with clear documentation OR
- Add simple message-based file tracking (10 lines of code max)

## Non-Issues (Working Fine)
- File upload - FIXED
- Stream analytics - FIXED
- Identity switching - WORKS
- Search tools - EXCELLENT
- Agent system - OPERATIONAL

## Test Commands

```bash
# Test type issue directly
uv run python -c "
from src.zulipchat_mcp.tools.messaging_v25 import search_messages
import asyncio
# Test with string '3' vs int 3
result = asyncio.run(search_messages(last_days='3'))
print(result)
"

# Check how FastMCP sees our tools
uv run python -c "
from src.zulipchat_mcp.server import main
# Inspect tool schemas that FastMCP generates
"
```

## Success Criteria
1. Claude Code can call `search_messages(last_days=3)` without errors
2. No type coercion inside tool functions
3. Fix at the MCP/FastMCP boundary only
4. Keep all working features untouched