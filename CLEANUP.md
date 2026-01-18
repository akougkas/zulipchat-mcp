# Type Safety Cleanup Plan

**Created**: 2026-01-17  
**Total Errors**: 131 errors across 17 files  
**Goal**: Full mypy compliance with strict type checking

---

## Overview

This plan addresses all mypy type errors systematically, organized by priority and complexity.

### Error Distribution by File

| File | Errors | Category |
|------|--------|----------|
| `core/client.py` | 24 | Zulip SDK API mismatches |
| `tools/search.py` | 22 | Dict type annotations |
| `core/identity.py` | 15 | Missing annotations + ConfigManager |
| `tools/ai_analytics.py` | 13 | FastMCP Content type unions |
| `tools/commands.py` | 12 | Abstract classes + imports |
| `core/error_handling.py` | 10 | Missing annotations |
| `core/commands/engine.py` | 4 | Missing annotations |
| `core/validation/narrow.py` | 4 | Missing annotations |
| `core/validation/validators.py` | 4 | Missing annotations + stubs |
| `utils/narrow_helpers.py` | 4 | Missing annotations |
| `tools/schedule_messaging.py` | 4 | Type assignment |
| `tools/topic_management.py` | 4 | Argument types |
| `tools/agents.py` | 3 | Type mismatches |
| `services/scheduler.py` | 3 | Missing named argument |
| `tools/files.py` | 2 | Argument types |
| `services/message_listener.py` | 1 | Missing attribute |
| `core/service_manager.py` | 1 | Unused ignore |

---

## Phase 1: Dependencies & Configuration (Quick Wins)

**Estimated Time**: 15 minutes  
**Errors Fixed**: ~5

### 1.1 Install Missing Type Stubs

```bash
uv add --dev types-requests types-python-dateutil
```

**Files affected**:
- `core/client.py:649` - `requests` import
- `core/validation/validators.py:188` - `dateutil` import

### 1.2 Fix Unused `type: ignore` Comments

Remove or update stale `# type: ignore` comments:

| File | Line | Issue |
|------|------|-------|
| `core/identity.py` | 387, 405, 408 | Unused ignore (wrong error code) |
| `tools/commands.py` | 40, 63, 109 | Unused ignore |
| `core/service_manager.py` | 77 | Unused ignore |

**Action**: Either remove the comments or specify correct error codes like `# type: ignore[return-value]`

---

## Phase 2: Missing Type Annotations (Medium Effort)

**Estimated Time**: 45 minutes  
**Errors Fixed**: ~30

### 2.1 `core/error_handling.py` (10 errors)

Add return type annotations:

```python
# Line 73
def __init__(self, ...) -> None:

# Line 94  
def __init__(self, ...) -> None:

# Line 149
def __init__(self, ...) -> None:

# Line 246
def decorator(func: Callable[..., T]) -> Callable[..., T]:

# Line 328, 334
def wrapper(*args: Any, **kwargs: Any) -> T:

# Line 347 - Complex return type fix
# Line 368, 396 - Add return types
```

**Type assignment fix** (Line 136):
```python
self._last_refill: float = time.time()  # Change from int to float
```

### 2.2 `core/commands/engine.py` (4 errors)

Add type annotations to lines 211, 277, 354, 415:
```python
def method(self, param: SomeType) -> ReturnType:
```

### 2.3 `core/validation/narrow.py` (4 errors)

Add annotations to lines 39, 55, 98, 112.

### 2.4 `core/validation/validators.py` (4 errors)

- Line 21: Add `-> None` return type
- Lines 442, 453: Fix datetime vs int assignment

### 2.5 `utils/narrow_helpers.py` (4 errors)

Add annotations to lines 460, 488, 513, 649.

---

## Phase 3: Zulip Client Wrapper (Complex)

**Estimated Time**: 1-2 hours  
**Errors Fixed**: 24

### 3.1 `core/client.py` - SDK API Signature Issues

The `ZulipClientWrapper` wraps the Zulip SDK but uses different signatures. Options:

**Option A**: Use `call_endpoint` for all mismatched methods (recommended)
**Option B**: Match SDK signatures exactly
**Option C**: Add `# type: ignore[call-arg]` with explanatory comments

#### Specific Fixes Needed:

| Line | Method | Issue | Fix |
|------|--------|-------|-----|
| 96-97 | `_create_client` | Return type | Fix `Optional[Client]` handling |
| 320 | `update_subscription_settings` | `subscriptions` → `subscription_data` | Rename kwarg |
| 360 | `add_subscriptions` | Dict vs Iterable | Wrap in list |
| 367 | `remove_subscriptions` | Wrong kwarg | Use correct signature |
| 376 | `update_stream` | `stream_id` → `stream_data` | Use dict format |
| 400, 408 | `get_subscribers` | Too many args | Use correct signature |
| 428 | `mute_topic` | Wrong kwargs | Match SDK signature |
| 518 | `get_user_by_id` | Dict vs int | Extract int from dict |
| 550 | `update_message_flags` | Wrong kwargs | Use `request` dict format |
| 574 | `deregister` | Dict vs str | Extract queue_id |
| 585 | `get_events` | Too many args | Use correct signature |
| 604-605 | `update_presence` | Wrong kwargs & type | Match SDK signature |
| 646 | `upload_file` | bytes vs IO | Wrap bytes in BytesIO |

### 3.2 Recommended Approach

Create a compatibility layer that translates our API to SDK calls:

```python
def update_message_flags(
    self, messages: list[int], op: str, flag: str
) -> dict[str, Any]:
    """Update message flags using SDK's request format."""
    return self.client.update_message_flags(
        request={"messages": messages, "op": op, "flag": flag}
    )
```

---

## Phase 4: Identity Manager (Complex)

**Estimated Time**: 45 minutes  
**Errors Fixed**: 15

### 4.1 `core/identity.py`

#### Missing Return Types (Lines 55, 114, 178, 244, 466)
```python
def __init__(self, ...) -> None:
def method(self) -> None:
```

#### ConfigManager Attribute Errors (Lines 204-206)
```python
# Current (wrong):
config.email, config.api_key, config.site

# Fix - access through config.config:
config.config.email, config.config.api_key, config.config.site
```

#### Return Value Type Mismatches (Lines 387, 405, 408)
```python
# Current returns Identity | None but signature says Identity
# Fix: Add Optional return type or ensure non-None return
def get_identity(self) -> Identity | None:
    ...
```

#### Line 414 - Generic Callable
```python
# Add type parameters
Callable[[ParamType], ReturnType]
```

#### Line 446 - var-annotated
```python
result: dict[str, Any] = {}
```

#### Line 456 - Indexed assignment
Handle the union type properly with type narrowing.

---

## Phase 5: Tool Modules (Medium Effort)

**Estimated Time**: 1 hour  
**Errors Fixed**: ~60

### 5.1 `tools/search.py` (22 errors)

All errors are Dict type mismatches for `negated` field:

```python
# Current (wrong type inference):
{"operator": "has", "operand": "attachment", "negated": True}

# Fix Option A - Use Any for narrow dicts:
narrow: list[dict[str, Any]] = []

# Fix Option B - Define proper TypedDict:
class NarrowFilter(TypedDict, total=False):
    operator: str
    operand: str
    negated: bool
```

**Affected lines**: 146, 152, 158, 165, 171, 177, 519, 526, 532, 539, 545, 552, 559, 565, 572, 594, 597, 604, 607

### 5.2 `tools/ai_analytics.py` (13 errors)

FastMCP Content type union issues:

```python
# Current:
response.content[0].text  # Error: not all union members have .text

# Fix - Add type narrowing:
from mcp.types import TextContent

content = response.content[0]
if isinstance(content, TextContent):
    text = content.text
```

**Affected lines**: 97, 188, 286

**Line 157** - Add dict annotation:
```python
by_stream: dict[str, list[dict[str, Any]]] = {}
```

### 5.3 `tools/commands.py` (12 errors)

#### Line 69 - Import error
```python
# Remove or fix import of non-existent module:
# from zulipchat_mcp.tools.search_v25 import ...
from zulipchat_mcp.tools.search import ...
```

#### Lines 135, 137, 145 - Abstract class instantiation
Implement `_rollback_impl` method in subclasses or make them concrete.

#### Lines 40, 63, 109 - Missing annotations
Add proper type hints.

### 5.4 `tools/schedule_messaging.py` (4 errors)

Lines 114-120 - Fix type assignments:
```python
# The variable is typed as Literal but assigned wrong types
# Fix: Use proper typing or widen the type
message_type: str = ...  # Instead of Literal
```

### 5.5 `tools/topic_management.py` (4 errors)

Lines 98, 117, 133, 146 - Fix argument types:
```python
# Ensure stream_id is int, not Any | None
stream_id: int = validated_stream_id
```

### 5.6 `tools/files.py` (2 errors)

Lines 99, 108 - Handle `None` case:
```python
if file_content is None:
    return {"status": "error", "error": "No file content"}
validate_file_security(file_content)
```

### 5.7 `tools/agents.py` (3 errors)

- Line 170: Type annotation fix
- Lines 348, 351: List type mismatch (str vs int)

---

## Phase 6: Services (Quick)

**Estimated Time**: 20 minutes  
**Errors Fixed**: 4

### 6.1 `services/message_listener.py` (1 error)

Line 45 - Add missing `_process_message` method or fix reference.

### 6.2 `services/scheduler.py` (3 errors)

Lines 230, 268, 321 - Add missing `scheduled_id` argument:
```python
ScheduledMessage(scheduled_id=some_id, ...)
```

---

## Execution Checklist

### Pre-flight
- [ ] Create a new branch: `git checkout -b fix/mypy-cleanup`
- [ ] Ensure tests pass before starting: `uv run pytest -q`

### Phase 1: Dependencies (~15 min)
- [ ] Add type stubs: `uv add --dev types-requests types-python-dateutil`
- [ ] Remove/fix unused `# type: ignore` comments
- [ ] Run `uv run mypy src` - verify stub errors resolved

### Phase 2: Missing Annotations (~45 min)
- [ ] Fix `core/error_handling.py`
- [ ] Fix `core/commands/engine.py`
- [ ] Fix `core/validation/narrow.py`
- [ ] Fix `core/validation/validators.py`
- [ ] Fix `utils/narrow_helpers.py`
- [ ] Run `uv run mypy src` - verify ~30 errors resolved

### Phase 3: Zulip Client (~1-2 hr)
- [ ] Document SDK signature differences
- [ ] Implement compatibility layer in `core/client.py`
- [ ] Test each fixed method
- [ ] Run `uv run mypy src` - verify ~24 errors resolved

### Phase 4: Identity Manager (~45 min)
- [ ] Fix return types
- [ ] Fix ConfigManager access
- [ ] Fix type narrowing issues
- [ ] Run `uv run mypy src` - verify ~15 errors resolved

### Phase 5: Tool Modules (~1 hr)
- [ ] Fix `tools/search.py` - narrow dict types
- [ ] Fix `tools/ai_analytics.py` - Content type narrowing
- [ ] Fix `tools/commands.py` - abstract classes + imports
- [ ] Fix remaining tool files
- [ ] Run `uv run mypy src` - verify ~60 errors resolved

### Phase 6: Services (~20 min)
- [ ] Fix `services/message_listener.py`
- [ ] Fix `services/scheduler.py`
- [ ] Run `uv run mypy src` - should be 0 errors

### Post-flight
- [ ] Run full test suite: `uv run pytest -q`
- [ ] Run linting: `uv run ruff check . && uv run black .`
- [ ] Commit: `git commit -m "fix: Resolve all mypy type errors"`

---

## Notes

### Why These Errors Exist

1. **Rapid prototyping** - Type hints were deprioritized during initial development
2. **SDK evolution** - Zulip SDK signatures may have changed
3. **v0.4 refactor** - Module consolidation left some type inconsistencies
4. **FastMCP types** - New MCP types weren't fully integrated

### Risk Areas

- `core/client.py` - Changes here affect all tools; test thoroughly
- `core/identity.py` - Core auth logic; be careful with type changes
- `tools/search.py` - High-use module; ensure narrow filters still work

### Testing Strategy

After each phase:
```bash
uv run mypy src                    # Type check
uv run pytest -q                   # Unit tests
uv run pytest -q -m "not slow"     # Quick feedback
```

---

## Estimated Total Time

| Phase | Time |
|-------|------|
| Phase 1: Dependencies | 15 min |
| Phase 2: Annotations | 45 min |
| Phase 3: Client Wrapper | 1-2 hr |
| Phase 4: Identity | 45 min |
| Phase 5: Tools | 1 hr |
| Phase 6: Services | 20 min |
| **Total** | **4-5 hours** |

---

*Last updated: 2026-01-17*
