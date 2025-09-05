# ZulipChat MCP Refactoring and Cleanup Plan

**Objective:** Address critical bugs, reduce complexity, and improve the architectural integrity of the `zulipchat-mcp` server.

---

### Part 1: Critical Bug Fixes (Based on User Debug Report)

These issues directly impact core functionality and must be addressed first.

-   **[ ] 1.1. Fix Stream Creation & Agent Registration:**
    -   **Issue:** `create_stream` returns `"Stream created but ID not found"`, which causes `register_agent` to fail.
    -   **Analysis:** The Zulip API response for stream creation is likely not being parsed correctly in `tools/stream_management.py`.
    -   **Action:**
        1.  Inspect the `create_stream` method in `src/zulipchat_mcp/tools/stream_management.py`.
        2.  Correct the logic to properly extract the `stream_id` from the API response.
        3.  Verify that fixing this also resolves the `register_agent` failure.

-   **[ ] 1.2. Fix Message Scheduling:**
    -   **Issue:** `schedule_message` fails with an `HTTPStatusError`.
    -   **Analysis:** This points to an incorrect API call structure in `src/zulipchat_mcp/scheduler.py`. The Zulip API for scheduling messages is new and might have specific requirements.
    -   **Action:**
        1.  Review the `schedule_message` method in `src/zulipchat_mcp/scheduler.py`.
        2.  Consult the official Zulip API documentation for scheduling messages and correct the API request payload.

### Part 2: Architectural Refactoring (Based on Gemini's Review)

These changes will simplify the codebase, remove technical debt, and improve long-term maintainability.

-   **[ ] 2.1. Purge Legacy and Unused Code:**
    -   **Issue:** The `async_client.py` and `assistants.py` modules are orphaned remnants from a previous design and are not used by the main server.
    -   **Action:**
        1.  Delete `src/zulipchat_mcp/async_client.py`.
        2.  Delete `src/zulipchat_mcp/assistants.py`.
        3.  Remove any lingering imports of these files (e.g., in `notifications.py`).
        4.  Remove the associated tests in `tests/test_async.py` and `tests/test_assistants.py` to reflect the leaner codebase.

-   **[ ] 2.2. Simplify State Management:**
    -   **Issue:** The multi-table SQLite database is over-engineered for local state management. The `wait_for_response` function uses an inefficient blocking poll.
    -   **Action:**
        1.  Delete `src/zulipchat_mcp/database.py`.
        2.  Delete `src/zulipchat_mcp/tools/task_tracking.py`.
        3.  Remove the complex agent/task management tools (`register_agent`, `start_task`, `update_task_progress`, `complete_task`, `agent_message`, `wait_for_response`, `list_instances`, `cleanup_old_instances`) from `server.py`.
        4.  Create a simplified, session-based `agent_message` tool that sends a notification to a user-specified stream without database persistence. This retains the core notification feature while removing massive complexity.

-   **[ ] 2.3. Unify Data Flow:**
    -   **Issue:** Redundant and inefficient data conversions between Pydantic models and dictionaries across the client and server layers.
    -   **Action:**
        1.  Modify methods in `src/zulipchat_mcp/client.py` (e.g., `get_streams`, `get_users`) to *always* return Pydantic model objects, not dictionaries.
        2.  Refactor the corresponding MCP tools in `server.py` to expect these Pydantic objects, removing all `hasattr` checks and data re-conversion logic.

-   **[ ] 2.4. Fix Core Logic Bugs:**
    -   **Issue:** The `hours_back` filter in `get_messages_from_stream` is non-functional. The AFK logic is inverted.
    -   **Action:**
        1.  Correct `get_messages_from_stream` in `client.py` to use a proper time-based filter in its API call.
        2.  The AFK feature will be removed as part of the state management simplification (2.2), resolving the logic bug by removing the feature.

---
