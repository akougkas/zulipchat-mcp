# Failures Report — Triage and Fix Plan

Command: `uv run pytest -q` (full suite, gate 75%)
Date: 2025-09-12

Summary: 16 failures clustered around messaging v2.5 bulk ops, search v2.5 helpers, and mock client interfaces surfaced by recent imports and the new stream analytics path.

**Top Issues (Prioritized)**
- Variable reference bug in `messaging_v25.bulk_operations` inner closures (`api_narrow` vs `selection_narrow`).
- Test fakes don’t implement `get_messages_raw`; tools call `client.get_messages_raw(...)` consistently.
- Assertion/text drift in validation errors and message-sending signatures (private `to` list vs string; exact error strings).

**Failure Clusters**
- Messaging v2.5 – Bulk Ops
  - tests/tools/test_messaging_v25.py::TestBulkOperationsTool::test_bulk_operations_validation_errors
  - tests/tools/test_messaging_v25_bulk_and_edges.py::{test_bulk_add_remove_flag_success_and_conflict_error,test_bulk_add_remove_reaction_and_delete_success,test_bulk_narrow_paths_mark_read_flag_reaction_delete,test_bulk_add_reaction_no_messages_narrow}
  - tests/tools/test_messaging_v25_more.py::test_bulk_operations_read_with_narrow_and_add_flag_error

- Messaging v2.5 – Send/Cross-post
  - tests/tools/test_messaging_v25_bulk_and_edges.py::test_message_send_private_and_schedule_error_and_truncate
  - tests/tools/test_messaging_v25_more.py::test_cross_post_message_success

- Search v2.5 and Analytics
  - tests/tools/test_messaging_v25_search_edit_history.py::test_search_messages_basic_success
  - tests/tools/test_search_v25_aggregations.py::test_advanced_search_aggregations_and_cache
  - tests/tools/test_search_v25_aggregations_more.py::test_advanced_search_aggregations_counts
  - tests/tools/test_search_v25_analytics.py::test_analytics_activity_chart_data
  - tests/tools/test_search_v25_analytics_more.py::{test_analytics_sentiment_detailed_by_user,test_analytics_topics_group_by_stream,test_analytics_participation_chart_overall}
  - tests/tools/test_search_v25_errors_cache.py::test_advanced_search_cache_hit

---

## Root Causes and Precise Fixes

1) NameError and wrong variable check in bulk ops closures
- Symptom: NameError `api_narrow` and wrong branch choice inside `_execute_bulk_op` handlers.
- Cause: Selection is stored in `selection_narrow`, but inner logic checks `api_narrow`.
- Fix (code): Replace `if api_narrow:` with `if selection_narrow:` in bulk ops branches for flag/reaction/delete.
- Pointers: src/zulipchat_mcp/tools/messaging_v25.py around the handlers for `add_flag`, `remove_flag`, `add_reaction`, `remove_reaction`, `delete_messages`.
- Quick grep: `rg -n "selection_narrow|api_narrow" src/zulipchat_mcp/tools/messaging_v25.py`

2) Fake client interface mismatch: `get_messages_raw`
- Symptom: Tests using narrow paths fail because fakes only implement `get_messages(...)`.
- Contract: Tools prefer `ZulipClientWrapper.get_messages_raw(...)` for performance and parity with search helpers.
- Fix (tests): Add a `get_messages_raw(**kwargs)` method to fakes that delegates to existing `get_messages(request)` or returns a shaped response. Example stub:
  ```py
  def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):
      return self.get_messages({"anchor": anchor, "num_before": num_before, "num_after": num_after, "narrow": narrow or []})
  ```
- Affected tests: all listed under “Search v2.5 and Analytics” and the messaging v2.5 narrow-path tests.

3) Validation message text drift
- Symptom: tests expect “Must provide either narrow filters or message_ids” and “Cannot specify both narrow and message_ids”.
- Current impl: “Must provide message selection: use stream/topic/sender, narrow filters, or message_ids” and “Cannot specify multiple selection methods: choose one of simple params, narrow, or message_ids”.
- Decision: Keep the clearer, expanded messages (reflects new simple-selection support) and relax tests to assert status=error and that the message contains a stable substring (e.g., startswith("Must provide") / contains("message_ids")).

4) Private message recipient type
- Symptom: mismatch `'user@example.com'` vs `['user@example.com']` in `test_message_send_private_and_schedule_error_and_truncate`.
- Contract: Zulip API expects list for private `to`; wrapper coerces to list. Tests should expect a list.
- Fix (tests): Expect list input/behavior for private messages.

5) Cross-post payload shape
- Symptom: “error” on cross-post success test due to send signature differences.
- Contract: Cross-post calls underlying client `send_message` with dict payload; ensure fake implements that shape or add an adapter.
- Fix (tests): Provide `send_message(self, payload: dict)` in fake returning `{"result": "success"}`.

---

## Minimal Patch Plan (Code + Tests)

- Code: messaging_v25
  - [ ] Replace `if api_narrow:` with `if selection_narrow:` in three branches (flag, reaction, delete).
  - [ ] Sanity pass for similar shadowed names in messaging/search v2.5.

- Tests: fakes and strict assertions
  - [ ] Add `get_messages_raw` delegation helper to affected fakes in:
    - tests/tools/test_messaging_v25_bulk_and_edges.py
    - tests/tools/test_messaging_v25_more.py
    - tests/tools/test_messaging_v25_search_edit_history.py
    - tests/tools/test_search_v25_*.py
  - [ ] Relax assertion on validation error copy to allow new wording.
  - [ ] Expect list for private message recipients; adjust fake signatures accordingly.
  - [ ] Ensure cross-post fake supports dict payload in `send_message`.

---

## Quick Repro Commands

- Bulk ops targeted: `uv run pytest -q -k "bulk_operations and (edges or validation)"`
- Narrow-path messaging: `uv run pytest -q tests/tools/test_messaging_v25_bulk_and_edges.py -q`
- Search/analytics cluster: `uv run pytest -q -k "search_v25 or analytics"`

---

## Exit Criteria
- All 16 failures pass locally with `uv run pytest -q`.
- Coverage remains ≥ 75% (expect a small bump as narrow paths execute).
- No changes to public tool signatures; only error text clarified and internal variable fix.

## Notes
- The recent `streams_v25.stream_analytics` additions increased imports/execution of messaging/search helpers under coverage. The fixes above stabilize those paths without reverting analytics changes.

## Environment
- Runner: uv
- Command: `uv run pytest -q`
- Integration: skipped (no credentials)
