# HLD: Define Execution Backend Contract in AgentConfig

**Ticket:** #429 · `2a1b7787-0407-4fe5-8729-5ead280eed63`  
**Module:** `freedom-agents`  
**Status:** Todo → HLD

---

## Problem

`AgentConfig` fields like `toolsets` are silently ignored when the config is consumed by any path other than `Agent._create_pydantic_agent()`. There is no declared intent in the config itself about which execution backend it targets, making contract violations invisible at definition time.

---

## Proposed Change

### 1. Add `execution_backend` to `AgentConfig` (agent.py)

```python
@dataclass(slots=True)
class AgentConfig:
    instructions: str
    execution_backend: Literal["pydantic_ai", "pi_worker"] = "pydantic_ai"
    # ... existing fields unchanged
```

- Type: `Literal["pydantic_ai", "pi_worker"]`
- Default: `"pydantic_ai"` — all existing call sites are unaffected.
- One-line docstring on the field explaining its purpose and allowed values.

### 2. Add `__post_init__` validation

```python
def __post_init__(self):
    valid = {"pydantic_ai", "pi_worker"}
    if self.execution_backend not in valid:
        raise ValueError(
            f"execution_backend must be one of {valid!r}, got {self.execution_backend!r}"
        )
```

`@dataclass(slots=True)` is compatible with `__post_init__`; no structural change to the class is needed.

### 3. `Agent` unchanged

`Agent.__init__` does **not** inspect `execution_backend`. It is a pydantic_ai runner and simply ignores the field. The consumer of a config (e.g. a future pi-worker dispatcher) is responsible for detecting a mismatch.

---

## Data Flow (unchanged)

```
Caller builds AgentConfig(execution_backend="pydantic_ai"|"pi_worker")
  → __post_init__ validates the literal; raises ValueError on unknown values
  → Config passed to Agent / ManagedAgent / Temporal activity as today
  → Agent._create_pydantic_agent() proceeds as before; ignores execution_backend
```

The field is metadata — it documents intent and enables future consumers to branch on it without touching the `Agent` class.

---

## Files Touched

| File | Change |
|------|--------|
| `agent.py` | Add `execution_backend` field + `__post_init__` to `AgentConfig` |
| `tests/unit/test_agent.py` | Add 4 new test cases (see below) |

**No other files change.** All existing `AgentConfig(instructions=...)` call sites keep working because the field has a default.

---

## Test Plan

New test cases in `tests/unit/test_agent.py`:

1. `test_agent_config_default_execution_backend` — `AgentConfig(instructions="x").execution_backend == "pydantic_ai"`
2. `test_agent_config_pi_worker_backend_valid` — `AgentConfig(instructions="x", execution_backend="pi_worker")` constructs without error
3. `test_agent_config_invalid_backend_raises` — `AgentConfig(instructions="x", execution_backend="invalid")` raises `ValueError`
4. `test_agent_accepts_pi_worker_config` — `Agent(config=AgentConfig(instructions="x", execution_backend="pi_worker"))` constructs without error (mocking PydanticAgent)

---

## Acceptance Criteria

1. `AgentConfig` has `execution_backend: Literal["pydantic_ai", "pi_worker"] = "pydantic_ai"`.
2. All existing `AgentConfig` call sites work without modification.
3. `AgentConfig(instructions="...", execution_backend="pi_worker")` constructs without error.
4. `AgentConfig(instructions="...", execution_backend="invalid")` raises `ValueError` in `__post_init__`.
5. `Agent(config=AgentConfig(instructions="...", execution_backend="pi_worker"))` does not raise.
6. The field has a one-line docstring explaining its purpose.
7. `from agents.core.agent import AgentConfig` still works; the field is visible in `__dataclass_fields__`.

---

## Out of Scope

- Wiring `toolsets` for the pi-worker path via `PiMcpBridge`
- A `PiWorkerAgent` runner class
- Per-field cross-validation (e.g. blocking `toolsets` on `pi_worker` configs)
