Testing Plan: Transformation-Layer Unit Suite (v1)

Scope
- Validate transformation/business logic for v2.5 tools using fast, offline unit tests.
- Focus on parameter processing, calculations, response shaping, and error branching.
- Be explicit about non-goals (integration/security/network/E2E).

What Unit Tests Cover
- Parameter transformation and validation logic
- Business calculations: aggregations, insights, analytics math
- Response formatting: counts, has_more, metadata, chart_data, detailed_insights
- Error branching and exception handling
- Message processing/filtering/search logic
- Time ranges: TimeRange → narrow filters and boundary math

Non-Goals
- Live Zulip API calls, auth/security, DB operations
- MCP protocol conformance and end-to-end workflows
- Network error handling

Enhancements Roadmap
1) Shared fixtures/factories (reduce fake client/make_msg duplication)
2) Edge and boundary tests (limit±1, DST/time edges, zero-length ranges)
3) Contract tests for response shapes (jsonschema or structured asserts)
4) Error message/branching validations (structured error fields)
5) Insight validation: daily summaries and analytics math

Execution Steps
- Step 1: Introduce shared fixtures/factories in tests/conftest.py and refactor 3–5 tests to use them.
- Step 2: Add contract schemas + validators for key outputs (analytics, daily_summary, search results).
- Step 3: Add boundary tests for has_more/time ranges; convert error assertions to structured checks.
- Step 4: Fill remaining uncovered error branches across tools (fast, targeted).
- Step 5: Document scope/boundaries in TESTS.md and maintain runtime ≤ 7s.

Status
- Baseline coverage ≥90% with gate enforced.
- Proceeding with Step 1.

