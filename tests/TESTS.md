# inflight-py Test Documentation

## Overview

The test suite contains **58 tests** across **7 test files**, using `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`). All tests are async and exercise the `InFlight` class and `InFlightConflictError` exception.

### Running Tests

```bash
py -3.11 -m pytest -v
```

### Configuration

Configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Test Files

| File | Tests | Focus |
|------|-------|-------|
| `test_execute.py` | 7 | Core `execute()` fan-in deduplication |
| `test_execute_or_reject.py` | 7 | `execute_or_reject()` single-flight rejection |
| `test_inflight.py` | 5 | `has()`, `clear()`, `size`, `InFlightConflictError` |
| `test_cancellation.py` | 9 | Cancellation propagation and recovery |
| `test_lifecycle.py` | 9 | Task lifecycle, `clear()` semantics |
| `test_timing.py` | 7 | Concurrent timing, 3+ callers, staggered arrivals |
| `test_edge_cases.py` | 13 | Boundary conditions, types, isolation |

---

## test_execute.py

Tests for `InFlight.execute()` — the fan-in deduplication method where concurrent callers share the same result.

| Test | Description | Key Assertion |
|------|-------------|---------------|
| `test_two_simultaneous_calls_same_key_execute_once` | Two tasks created for the same key; only one function call is made | `call_count == 1`, both callers get `"result"` |
| `test_different_keys_both_execute` | Different keys are tracked independently | `call_count == 2`, size increments/decrements per key |
| `test_resolves_key_removed` | After successful completion, key is removed from tracking | `has("k") == False`, `size == 0` |
| `test_rejects_key_removed` | After an exception, key is still removed (finally block) | `has("k") == False`, `size == 0` |
| `test_new_call_after_rejection_executes_again` | After a failure, a new call for the same key runs the function again | `call_count == 2`, result is `"ok"` |
| `test_new_call_after_completion_executes_again` | After success, a new call for the same key runs the function again (no cross-sequence dedup) | `a == 1`, `b == 2` |
| `test_concurrent_callers_receive_same_result` | Two concurrent callers get the exact same object reference (`a is b`) | Identity check for both success and exception cases |

### Patterns Tested

- **Fan-in deduplication**: N callers for the same key → 1 function call → N identical results
- **Key lifecycle**: Keys are added on call, removed in `finally` block
- **Sequential calls**: After completion, same key can be called again (no cross-sequence dedup)
- **Exception cleanup**: Failed calls still clean up the key via `finally`

---

## test_execute_or_reject.py

Tests for `InFlight.execute_or_reject()` — the single-flight method that rejects duplicate callers with `InFlightConflictError`.

| Test | Description | Key Assertion |
|------|-------------|---------------|
| `test_first_call_executes` | First call succeeds normally | `result == "ok"`, `size == 0` after |
| `test_second_call_inflight_rejects_with_conflict` | Second concurrent call raises `InFlightConflictError` | Exception message matches `'inflight conflict for "k"'` |
| `test_rejects_with_correct_query_key` | The exception's `.query_key` attribute matches the key used | `exc_info.value.query_key == "my-key"` |
| `test_different_keys_both_execute` | Different keys run independently | Both succeed, `size == 0` |
| `test_after_completion_can_execute_again` | After success, same key can be used again | `a == 1`, `b == 2` |
| `test_after_rejection_can_execute_again` | After function failure, subsequent call for same key works | First raises `RuntimeError`, second returns `"ok"` |
| `test_concurrent_callers_get_same_rejection` | Two simultaneous callers both get `InFlightConflictError` | Both exceptions carry the same `query_key` |

### Patterns Tested

- **Single-flight rejection**: Only the first caller executes; others are rejected immediately
- **Exception attributes**: `InFlightConflictError` stores the conflicting key
- **Recovery**: After failure or rejection, the key is freed for new calls

---

## test_inflight.py

Tests for `InFlight` utility methods and `InFlightConflictError`.

| Test | Description | Key Assertion |
|------|-------------|---------------|
| `test_has_returns_false_initially` | Empty `InFlight` returns `False` for `has()` | `has("k") == False`, `size == 0` |
| `test_clear_specific_key` | `clear("a")` removes one tracked key | `size` drops from 1 to 0 |
| `test_clear_all` | `clear()` (no argument) removes all tracked keys | `size` drops from 2 to 0 |
| `test_size_tracks_tasks` | `size` accurately reflects 0 → 1 → 2 → 0 | Size updates as tasks are created and complete |
| `test_conflict_error_attributes` | `InFlightConflictError` stores `.query_key` and formats message | `err.query_key == "test-key"`, message contains key |

### Patterns Tested

- **State inspection**: `has()` and `size` for monitoring tracked tasks
- **Manual cleanup**: `clear()` for specific keys or all keys
- **Error formatting**: `InFlightConflictError` is readable and carries context

---

## test_cancellation.py

Tests for cancellation behavior — what happens when tasks are cancelled while in-flight.

| Test | Description | Key Assertion |
|------|-------------|---------------|
| `test_cancel_first_caller_second_also_cancelled` | Cancelling the first caller also cancels the second (shared task) | Both raise `CancelledError` |
| `test_cancel_second_caller_also_cancels_first` | Cancelling the second caller also cancels the first (shared task) | Both raise `CancelledError` |
| `test_cancel_first_caller_execute_or_reject_second_rejected` | For `execute_or_reject`, cancelling first caller doesn't affect rejected second caller | First: `CancelledError`, Second: `InFlightConflictError` |
| `test_cancel_second_caller_execute_or_reject_first_continues` | For `execute_or_reject`, rejected second caller's state doesn't affect first | Second: `InFlightConflictError`, First: completes with `"done"` |
| `test_cancel_all_callers_key_removed` | Cancelling all callers still removes the key | `size == 0`, `has("k") == False` |
| `test_cancel_task_created_by_execute` | Cancelling the sole caller removes the key | `size == 0`, `has("k") == False` |
| `test_cancel_task_created_by_execute_or_reject` | Cancelling the sole caller removes the key | `size == 0`, `has("k") == False` |
| `test_new_call_after_cancel_executes_again` | After a cancelled call, a new call for the same key works | `call_count == 2`, result is `"ok"` |
| `test_concurrent_cancel_and_complete` | Cancelling one caller while the other completes — both get `CancelledError` | Shared task cancellation propagates |

### Key Behaviors Discovered

- **`execute()` shares the underlying `asyncio.Task`**: When one awaiter is cancelled, the cancellation propagates to all waiters because they share the same task object.
- **`execute_or_reject()` isolates callers**: The second caller is rejected immediately with `InFlightConflictError` and does not share the underlying task, so cancellation of one doesn't affect the other.
- **`finally` block always runs**: Whether the task succeeds, fails, or is cancelled, the key is removed from tracking.

---

## test_lifecycle.py

Tests for task lifecycle management, `has()` behavior, and `clear()` semantics.

| Test | Description | Key Assertion |
|------|-------------|---------------|
| `test_has_true_while_inflight` | `has()` returns `True` while task is running, `False` after | `has("k")` transitions correctly |
| `test_has_true_while_inflight_execute_or_reject` | Same for `execute_or_reject()` | `has("k")` transitions correctly |
| `test_clear_nonexistent_key` | `clear()` with a key that doesn't exist is a no-op | `size == 0` unchanged |
| `test_clear_all_empty` | `clear()` on empty `InFlight` is a no-op | `size == 0` unchanged |
| `test_clear_does_not_cancel_task` | `clear("k")` removes tracking but the task continues running | Task completes with `"done"` after clear |
| `test_clear_all_does_not_cancel_tasks` | `clear()` removes all tracking but tasks continue running | Both tasks complete with `"done"` after clear |
| `test_size_after_sequential_operations` | Size returns to 0 after each sequential call | `size == 0` after each `execute()` |
| `test_size_after_concurrent_operations` | Size tracks 0 → 1 → 2 → 3 → 0 as tasks are created and complete | Accurate size at each step |
| `test_has_tracks_multiple_keys` | `has()` independently tracks multiple keys | `has("a")`, `has("b")`, `!has("c")` |

### Key Behaviors

- **`clear()` is tracking-only**: It removes the key from the internal dict but does **not** cancel the underlying `asyncio.Task`. The task continues executing and can still return a result.
- **`has()` is real-time**: It reflects the current state of the internal dict, which is updated immediately on task creation and completion.

---

## test_timing.py

Tests for concurrent timing scenarios — multiple callers arriving at different times.

| Test | Description | Key Assertion |
|------|-------------|---------------|
| `test_first_completes_as_second_arrives` | First call completes before second starts — both execute | `result1 == result2 == "done"`, `size == 0` |
| `test_execute_or_reject_first_completes_as_second_arrives` | Same for `execute_or_reject()` | Both return `"done"` |
| `test_three_concurrent_callers` | Three callers for same key — only one executes | `call_count == 1`, all get `"result"` |
| `test_three_sequential_calls_all_execute` | Three sequential calls — all execute independently | `call_count == 3`, results are 1, 2, 3 |
| `test_staggered_arrivals_all_share` | Callers arrive at different times (10ms apart) — all share | `r1 is r2 is r3`, `call_count == 1` |
| `test_multiple_keys_concurrent_overlap` | Two keys with overlapping concurrent callers | Each key's callers share, different keys are independent |
| `test_execute_or_reject_three_concurrent` | One executor + two rejected callers | Both rejected callers get `InFlightConflictError` |

### Patterns Tested

- **Fan-in with 3+ callers**: Deduplication works beyond just 2 callers
- **Staggered timing**: Callers arriving at different event loop ticks still share the same task
- **Multi-key isolation**: Different keys don't interfere with each other's deduplication
- **Sequential vs concurrent**: Sequential calls execute independently; concurrent calls share

---

## test_edge_cases.py

Tests for boundary conditions, type handling, and instance isolation.

| Test | Description | Key Assertion |
|------|-------------|---------------|
| `test_empty_string_key` | Empty string `""` works as a valid key | `result == "ok"` |
| `test_empty_string_key_execute_or_reject` | Same for `execute_or_reject()` | `result == "ok"` |
| `test_return_none` | `None` is a valid return value | `result is None` |
| `test_return_dict` | Dicts are returned correctly | `result == {"key": "value", "count": 42}` |
| `test_return_list` | Lists are returned correctly | `result == [1, 2, 3]` |
| `test_multiple_instances_isolated` | Two `InFlight` instances don't share state | Each has `size == 1` independently |
| `test_inflight_conflict_error_is_exception` | `InFlightConflictError` is an `Exception` subclass | `isinstance(err, Exception)` |
| `test_inflight_conflict_error_str` | String representation includes the key | `str(err) == 'inflight conflict for "my-key"'` |
| `test_inflight_conflict_error_query_key` | `.query_key` attribute stores the key | `err.query_key == "test-123"` |
| `test_long_key` | 10,000-character key works | `result == "ok"` |
| `test_special_characters_in_key` | Various special characters in keys work | Spaces, slashes, colons, dots, dashes, etc. |
| `test_execute_return_value_identity` | `execute()` returns the exact object reference | `result is sentinel` |
| `test_execute_or_reject_return_value_identity` | Same for `execute_or_reject()` | `result is sentinel` |
| `test_concurrent_callers_same_identity_execute` | Concurrent callers get the same object reference | `r1 is r2 is sentinel` |

### Patterns Tested

- **Key boundary conditions**: Empty strings, very long strings, special characters
- **Return type handling**: `None`, dicts, lists, custom objects
- **Object identity**: Both methods preserve object identity (not just equality)
- **Instance isolation**: Multiple `InFlight` instances are fully independent

---

## Test Patterns and Techniques

### Common Patterns

1. **`asyncio.Event` for deterministic concurrency**: Instead of relying on `sleep()` timing, tests use `asyncio.Event()` to precisely control when tasks complete.

2. **`asyncio.sleep(0)` for task scheduling**: Yields to the event loop to ensure created tasks start running before assertions.

3. **`asyncio.create_task()` for concurrent execution**: Creates tasks that run concurrently with the test coroutine.

4. **`asyncio.gather()` for parallel awaiting**: Awaits multiple tasks simultaneously to test concurrent behavior.

5. **`nonlocal` for call counting**: Tracks how many times a function is called across multiple invocations.

6. **`return_exceptions=True`**: Allows `asyncio.gather()` to collect exceptions instead of raising them immediately.

### Key Implementation Details Verified

| Detail | Verified By |
|--------|-------------|
| `finally` block removes keys | `test_rejects_key_removed`, `test_cancel_task_created_by_execute` |
| `ensure_future` starts task immediately | `test_staggered_arrivals_all_share` |
| Same `Task` object shared | `test_concurrent_callers_receive_same_result` (identity check) |
| `clear()` doesn't cancel tasks | `test_clear_does_not_cancel_task`, `test_clear_all_does_not_cancel_tasks` |
| Cancellation propagates in `execute()` | `test_cancel_first_caller_second_also_cancelled` |
| Rejection isolates in `execute_or_reject()` | `test_cancel_first_caller_execute_or_reject_second_rejected` |
