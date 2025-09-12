# ZulipChat MCP v2.5.0 Testing Session Prompt

## Objective
Rebuild the test suite with a "less is more" mentality. Create a minimal but complete set of tests that align with the actual v2.5.0 implementation.

## Source of Truth
The implementation in `src/zulipchat_mcp/` is the authoritative source. Tests must align to what actually exists, not what we think should exist.

## Todo List (Use TodoWrite to track progress)
- [ ] Analyze existing test files and eliminate redundant/over-engineered tests
- [ ] Identify critical test gaps in v2.5.0 implementation
- [ ] Create focused tests for foundation components (identity, validation, error handling, migration)
- [ ] Create integration tests for 7 tool categories (messaging, streams, events, users, search, files, admin)
- [ ] Ensure backward compatibility tests for migration layer
- [ ] Create simple performance/smoke tests
- [ ] Remove excessive test artifacts and keep only essential test files
- [ ] Validate all tests pass and cover critical functionality

## Key Principles
1. **Test what exists** - No tests for imaginary functionality
2. **Mock external APIs** - Don't make real Zulip API calls in tests
3. **Focus on critical paths** - Error handling, parameter validation, tool functionality
4. **Keep it simple** - Avoid complex test hierarchies and over-mocking
5. **Fast execution** - Tests should run quickly for development workflow

## Implementation Structure to Test
```
Foundation Layer:
├── core/identity.py (IdentityManager - user/bot/admin switching)
├── core/validation.py (ParameterValidator - progressive disclosure)
├── core/error_handling.py (ErrorHandler - retry/rate limiting)
└── core/migration.py (MigrationManager - backward compatibility)

Tool Categories (7):
├── tools/messaging_v25.py (6 tools: message, search, edit, bulk, etc.)
├── tools/streams_v25.py (4 tools: manage streams/topics, analytics)
├── tools/events_v25.py (3 tools: register, poll, listen)
├── tools/users_v25.py (3 tools: manage users, identity, groups)
├── tools/search_v25.py (2 tools: advanced search, analytics)
├── tools/files_v25.py (2 tools: upload, manage)
└── tools/admin_v25.py (2 tools: operations, customize)
```

## Success Criteria
- [ ] All critical functionality covered with focused tests
- [ ] Test suite runs in <30 seconds
- [ ] No redundant or over-engineered test files
- [ ] Clear separation: unit tests for components, integration tests for workflows
- [ ] Migration layer backward compatibility verified
- [ ] Foundation components thoroughly tested (they're used by all tools)

## What NOT to do
- Don't create tests for functionality that doesn't exist
- Don't over-mock everything - use simple, focused mocks
- Don't create extensive test hierarchies or complex fixtures
- Don't generate multiple test summary/report files
- Don't test internal implementation details that could change

Focus on delivering a clean, minimal test suite that gives confidence in the v2.5.0 architecture without bloat.