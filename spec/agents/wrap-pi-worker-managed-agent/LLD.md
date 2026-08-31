# LLD: Wrap pi_worker Execution in ManagedAgent for AgentRun Persistence

**Ticket:** #431 · `a2768343-9628-4865-9956-6a89d71ea4d0`  
**Module:** `freedom-agents`  
**Phase:** LLD

---

## Scope

Two files change. No migrations, no new modules, no changes to existing call sites.

| File | Nature of change |
|------|-----------------|
| `agent.py` | Add `pi_worker_dispatch` param to `ManagedAgent.__init__`; branch in `_execute_run` |
| `tests/integration/test_managed_agent.py` | Add 2 new test functions |

---

## Step 1 — Add `pi_worker_dispatch` to `ManagedAgent.__init__`

`ManagedAgent.__init__` signature (current):
```
def __init__(self, agent=None, *, config=None, agent_label=None):
```

New signature:
```
def __init__(self, agent=None, *, config=None, agent_label=None, pi_worker_dispatch=None):
```

- Type annotation: `Optional[Callable[..., Any]]`
- Default: `None`
- Store as: `self._pi_worker_dispatch = pi_worker_dispatch`
- Placement: immediately after `self._started = False` and before the `AgentRun.objects.create(...)` call (line ~179 in agent.py).
- Add a one-line comment above the assignment: `# Injected callable for pi_worker backend dispatch.`

No other constructor logic changes.

---

## Step 2 — Branch in `ManagedAgent._execute_run`

`_execute_run` currently contains this block inside the `try:`:

```python
result = self._agent.run_sync(input_payload)
output = getattr(result, "output", getattr(result, "data", None))
output = _json_safe_value(output)
```

Replace these three lines with:

```python
if self._pi_worker_dispatch is not None:
    # Pi_worker path: dispatch returns output directly (not a pydantic_ai result).
    raw = self._pi_worker_dispatch(input_payload)
    output = _json_safe_value(raw)
else:
    result = self._agent.run_sync(input_payload)
    output = getattr(result, "output", getattr(result, "data", None))
    output = _json_safe_value(output)
```

The `except Exception` and `finally` blocks are **unchanged**. The persistence
contract (RUNNING → SUCCEEDED/FAILED, timestamps, signals) is identical for both
branches.

---

## Step 3 — Verify unchanged paths

`ManagedAgent.run` (async thread dispatch) and `ManagedAgent.run_sync` do not need
to change; they both call `_execute_run`. `run_agent` helper passes through
`ManagedAgent.__init__` kwargs, but does not need updating since it doesn't use
`pi_worker_dispatch`. Confirm by inspection that neither method references
`_pi_worker_dispatch` and would need updating.

---

## Step 4 — Add integration tests to `tests/integration/test_managed_agent.py`

Append two new test functions after the existing tests. Both are synchronous.

### 4a. `test_managed_agent_pi_worker_dispatch_succeeds`

```
- Define a lambda/function `pi_dispatch(payload)` that returns `{"pi_result": "ok"}`.
- Construct `ManagedAgent(agent=FakeAgentSuccess({"dummy": True}), pi_worker_dispatch=pi_dispatch, agent_label="pi-test")`.
- Call `managed.run_sync(input_payload={"q": "hi"})`.
- Assert `run.status == AgentRunStatus.SUCCEEDED`.
- Assert `run.output == {"pi_result": "ok"}`.
- Assert `output == {"pi_result": "ok"}` (return value of run_sync).
```

Note: `FakeAgentSuccess` is never called in the pi_worker path; its presence just
satisfies `ManagedAgent.__init__`. The dispatch callable is what runs.

### 4b. `test_managed_agent_pi_worker_dispatch_fails`

```
- Define a function `pi_dispatch(payload)` that raises `ValueError("pi blew up")`.
- Construct `ManagedAgent(agent=FakeAgentSuccess({"dummy": True}), pi_worker_dispatch=pi_dispatch, agent_label="pi-test")`.
- Call `managed.run_sync(input_payload={"q": "hi"})`.
- Assert `run.status == AgentRunStatus.FAILED`.
- Assert `"pi blew up" in run.error_message`.
- Assert return value of run_sync is `None` (run.output when FAILED).
```

---

## Acceptance Checklist

1. `ManagedAgent.__init__` accepts `pi_worker_dispatch` kwarg without breaking existing callers.
2. When `pi_worker_dispatch` is `None`, existing pydantic_ai behavior is unchanged.
3. When `pi_worker_dispatch` is set, it is called with `input_payload`; its return value is stored as `AgentRun.output` after `_json_safe_value`.
4. A raising `pi_worker_dispatch` results in `AgentRun.status == FAILED` and `error_message` set.
5. Signals (`agent_run_finished`, `agent_run_completed`) are fired for both pi_worker outcomes.
6. All pre-existing integration tests pass without modification.

---

## Invariants and Constraints

- `_execute_run` is called from both `run` (threaded) and `run_sync`; the branch logic is in one place.
- The pi_worker dispatch callable must be synchronous (called with no `await`).
- `_json_safe_value` handles arbitrary return types from the dispatch (dicts, dataclasses, enums).
- No changes to `run_agent`, `Agent`, `AgentConfig`, or any Temporal activity/workflow.
