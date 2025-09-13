# Critical Bugs - ZulipChat MCP v2.5.0

**Status**: Fixed (core wrapper methods + API signature fixes)  
**Tester**: Senior Engineer Beta Testing  
**Date**: 2025-09-12 (updated)  
**Environment**: Claude Code + ZulipChat MCP integration

## Summary

Testing revealed **systematic implementation gaps** in the `ZulipClientWrapper` that render core MCP functionality non-operational. These are not edge cases but fundamental method implementations missing from the wrapper layer.

## Critical Issues

### BUG-001: Missing Core Wrapper Methods
Status: Resolved in src/zulipchat_mcp/core/client.py

- Added implementations:
  - `get_user_by_email(email, include_custom_profile_fields=False)`
  - `get_user_by_id(user_id, include_custom_profile_fields=False)`
  - `get_message(message_id)`
  - `update_message_flags(messages, op, flag)`
  - `register(**kwargs)` / `deregister(queue_id)` / `get_events(**kwargs)`
  - Convenience: `update_user(user_id, **updates)`, `update_presence(status, ...)`

Implementation notes:
- Prefer native zulip.Client methods when available; gracefully fall back to `call_endpoint`.
- Support both kwargs and request-dict calling conventions to handle zulip-python version differences.

Verification:
- users_v25: get/update paths execute using new methods.
- messaging_v25: bulk mark read/flags and history paths call through successfully.
- events_v25: register/get_events/listen/deregister flows work with both kwargs and dict payloads.

### BUG-002: API Signature Mismatch - get_subscribers()
Status: Resolved in src/zulipchat_mcp/core/client.py

- Wrapper now calls underlying client with keyword: `get_subscribers(stream_id=...)`.
- Falls back to request-dict or REST path if needed.

Verification:
- streams_v25: `get_stream_info(..., include_subscribers=True)` returns subscriber list without TypeError.

### BUG-003: Stream Creation Parameter Mismatch
Status: Resolved in src/zulipchat_mcp/core/client.py

- `ZulipClientWrapper.add_subscriptions(...)` now accepts both `subscriptions=[...]` (preferred) and `streams=[...]` (legacy), plus optional `principals`, `announce`, and `authorization_errors_fatal`.
- Internally tries both zulip-python calling conventions; otherwise uses REST `users/me/subscriptions`.

Verification:
- streams_v25: `manage_streams(operation="create", stream_names=[...])` succeeds and returns `subscribed`/`already_subscribed` as expected.

## Working Functionality

**Verified Working** (70% of tested tools):
- Message search and content retrieval
- Stream listing and basic stream operations  
- User directory access
- Daily summaries and basic analytics
- Agent communication system
- Reaction management
- Stream settings retrieval

## Testing Notes

- Error handling is robust - no crashes, clean error messages returned
- Rate limiting is properly implemented (encountered during high-volume testing)
- Identity separation works correctly (user vs bot operations)
- Performance is acceptable (2-4s average response time)

## Environment Details

- Testing performed with user identity (akougkas@iit.edu) 
- Bot communications via Claude Code bot (ID: 956972)
- All testing isolated to private channels
- 40+ tools tested across all categories
