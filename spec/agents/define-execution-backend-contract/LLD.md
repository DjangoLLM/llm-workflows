# LLD: Define Execution Backend Contract in AgentConfig

**Ticket:** #429 · `2a1b7787-0407-4fe5-8729-5ead280eed63`  
**Module:** `freedom-agents`  
**Phase:** LLD

---

## Scope

Two files change. No migrations, no new modules, no changes to existing call sites.

| File | Nature of change |
|------|-----------------|
| `agent.py` | Add field + `__post_init__` to `AgentConfig` |
| `tests/unit/test_agent.py` | Add 4 new test functions |

---

## Step 1 — Add `Literal` to the `typing` import in `agent.py`

`agent.py` line 13 imports `Any, Callable, Iterable, Mapping, Optional` from `typing`.  
Add `Literal` to that same import. `Dict` is already imported separately on line 4; leave it untouched.

---

## Step 2 — Add the `execution_backend` field to `AgentConfig`

`AgentConfig` is a `@dataclass(slots=True)` declared at line 50 of `agent.py`.

Insert `execution_backend` as the **second** field, immediately after `instructions`.

- Type annotation: `Literal["pydantic_ai", "pi_worker"]`
- Default value: `"pydantic_ai"`
- Attach a one-line comment (not a docstring; slots dataclasses don't support PEP 257 field docstrings) directly above the field that reads: `# Declares which execution path this config targets; validated in __post_init__.`

Placing it second, after `instructions` (the only required field), ensures all existing `AgentConfig(instructions=...)` calls remain valid — Python dataclasses require fields without defaults to precede fields with defaults, and all other fields already have defaults.

---

## Step 3 — Add `__post_init__` to `AgentConfig`

`@dataclass(slots=True)` is fully compatible with `__post_init__`; no structural change to the class decorator is needed.

Add a `__post_init__` method to `AgentConfig` immediately after the field declarations.

Logic:
- Define a local constant `_VALID_BACKENDS` equal to the frozenset `{"pydantic_ai", "pi_worker"}`.
- If `self.execution_backend` is not in that set, raise `ValueError` with a message that includes both the received value and the set of valid values.

No other validation. No cross-field checks.

---

## Step 4 — Verify `Agent` requires no changes

`Agent.__init__` at line 65 and `Agent._create_pydantic_agent` at line 93 do not read `execution_backend`. No change is needed. Confirm by inspection that neither method references the field; if a future reader adds logic there it will be a separate ticket.

---

## Step 5 — Add unit tests to `tests/unit/test_agent.py`

Append four new test functions after the existing tests. All four are synchronous (no `asyncio`).

### 5a. `test_agent_config_default_execution_backend`

Construct `AgentConfig(instructions="x")` and assert `execution_backend == "pydantic_ai"`. No mocking required.

### 5b. `test_agent_config_pi_worker_backend_valid`

Construct `AgentConfig(instructions="x", execution_backend="pi_worker")`. Assert the instance is created without error and `execution_backend == "pi_worker"`. No mocking required.

### 5c. `test_agent_config_invalid_backend_raises`

Use `pytest.raises(ValueError)` as a context manager. Inside, construct `AgentConfig(instructions="x", execution_backend="invalid")`. Assert the `ValueError` is raised. Optionally match the error message against the received value string `"invalid"` to confirm the right check fired.

### 5d. `test_agent_accepts_pi_worker_config`

This test requires the same monkeypatch helper used by existing tests:
- Call `_patch_openai_model_construction(monkeypatch)` to stub model construction.
- Wrap `Agent(config=AgentConfig(instructions="x", execution_backend="pi_worker"))` in `mock.patch("agents.core.agent.PydanticAgent")`.
- Assert the call completes without error and `PydanticAgent` was called once (same assertion pattern as `test_agent_uses_explicit_config_with_string_model`).

---

## Acceptance checklist

These map 1-to-1 to the ticket's acceptance criteria.

1. `AgentConfig.__dataclass_fields__` contains `"execution_backend"` after the change.
2. All pre-existing tests continue to pass without modification.
3. Test 5b passes — `pi_worker` is accepted.
4. Test 5c passes — `"invalid"` raises `ValueError`.
5. Test 5d passes — `Agent` accepts a `pi_worker` config.
6. Field has the one-line comment per Step 2.
7. `from agents.core.agent import AgentConfig` works in a fresh import; field is present.

---

## Invariants and constraints

- `@dataclass(slots=True)` does not prevent `__post_init__`; Python generates `__init__` that calls it automatically.
- The `Literal` annotation is runtime-transparent — Python does not enforce it; enforcement is entirely in `__post_init__`.
- The `_VALID_BACKENDS` set in `__post_init__` must stay in sync with the `Literal` annotation. They are the single source of truth at their respective layers (static vs runtime).
- No Temporal activities, pipelines, or settings files reference `execution_backend`, so no downstream changes are needed for this ticket.
