# HLD: Wrap pi_worker Execution in ManagedAgent for AgentRun Persistence

**Ticket:** #431 · `a2768343-9628-4865-9956-6a89d71ea4d0`  
**Module:** `freedom-agents`  
**Phase:** HLD

---

## Problem

`ManagedAgent._execute_run` always calls `self._agent.run_sync(input_payload)`, which
dispatches through pydantic_ai regardless of `AgentConfig.execution_backend`. When the
caller supplies a pi_worker dispatch callable (e.g. wrapping the `PiMcpLoopWorkflow`
via Temporal or a direct HTTP call to the TS worker), `ManagedAgent` has no hook to
invoke it, so no `AgentRun` row is created or updated for the pi_worker path.

---

## Proposed Change

### 1. Add `pi_worker_dispatch` parameter to `ManagedAgent.__init__`

Accept an optional `pi_worker_dispatch: Optional[Callable[[Any], Any]] = None`.
Store it as `self._pi_worker_dispatch`. The callable receives `input_payload` and
returns the result directly (not wrapped in a pydantic_ai result object).

### 2. Branch in `ManagedAgent._execute_run`

When `self._pi_worker_dispatch is not None`, call it instead of `self._agent.run_sync`.
The return value is treated as the output directly (passed through `_json_safe_value`).
The existing `try / except / finally` persistence block is unchanged — AgentRun rows
transition PENDING → RUNNING → SUCCEEDED/FAILED identically to the pydantic_ai path.

---

## Data Flow (pi_worker path)

```
Caller builds ManagedAgent(agent=..., pi_worker_dispatch=<callable>)
  → AgentRun created PENDING
  → run_sync() called → status → RUNNING
  → _execute_run:
      if _pi_worker_dispatch is not None:
          raw = _pi_worker_dispatch(input_payload)   ← caller's pi dispatch
          output = _json_safe_value(raw)
      → AgentRun.output = output, status = SUCCEEDED
      → signals fired (agent_run_finished, agent_run_completed)
  on exception:
      → AgentRun.error_message = str(exc), status = FAILED
      → signals fired
```

---

## Files Touched

| File | Change |
|------|--------|
| `agent.py` | Add `pi_worker_dispatch` param to `ManagedAgent.__init__`; branch in `_execute_run` |
| `tests/integration/test_managed_agent.py` | Add 2 new test functions |

**No other files change.**

---

## Test Plan

1. `test_managed_agent_pi_worker_dispatch_succeeds` — inject a callable that returns a
   dict; assert `AgentRun.status == SUCCEEDED` and `output` matches the dict.
2. `test_managed_agent_pi_worker_dispatch_fails` — inject a callable that raises;
   assert `AgentRun.status == FAILED` and `error_message` contains the exception text.

---

## Out of Scope

- Implementing the actual TypeScript pi-worker call (Temporal workflow or HTTP).
- Validating that `pi_worker_dispatch` is provided when `execution_backend == "pi_worker"`.
- Changes to `Agent`, `run_agent`, or any pipeline/activity code.
