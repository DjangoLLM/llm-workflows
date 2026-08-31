# HLD: Typed pi-worker Agent Loop Contract

**Ticket:** #432 · `010649cd-9c09-464a-b69d-7a580e647410`  
**Module:** `freedom-agents`  
**Phase:** HLD

---

## Problem

The existing `Agent._create_pi_worker_dispatch_async` (agent.py:145) bypasses the LLM entirely — it calls a single MCP tool directly via `PiMcpBridge` using `tool_name` pulled from the raw `input_payload`. The actual agent loop (LLM inference → tool calls → tool execution → re-infer) is already implemented in `PiMcpLoopWorkflow` / `@mariozechner/pi-ai`, but the Agent class never routes to it.

Additionally, `AgentConfig.result_type` is ignored on the pi-worker path, so responses come back as untyped dicts with no validation.

---

## What Already Exists (unchanged)

- **`PiMcpLoopWorkflow`** orchestrates the multi-turn loop via Temporal activities.
- **TypeScript `piInference`** activity drives LLM inference using `@mariozechner/pi-ai`'s `complete()`.
- **`agents.mcp.list_pi_tools`** and **`agents.mcp.call_pi_tool`** activities handle tool discovery and invocation via `PiMcpBridge`.

Python does not manage the loop. It fires one request into `PiMcpLoopWorkflow` and waits for the final result.

---

## Proposed Change

Add a typed contract layer between `Agent` and `PiMcpLoopWorkflow` so that:

1. `AgentConfig.result_type` is the source of truth for the response shape.
2. A JSON Schema derived from `result_type` travels to the TS pi-worker, which validates its final output against it.
3. Python validates and coerces the returned payload back to the `result_type` instance.

The loop logic is **not changed**.

---

### 1. New contract module: `agents/tools/mcp/pi_loop_contract.py`

**`PiWorkerLoopRequest`** — typed input from `AgentConfig` into `PiMcpLoopWorkflow`:

```python
@dataclass(slots=True, frozen=True)
class PiWorkerLoopRequest:
    instructions: str           # system prompt → PiMcpLoopInput.system_prompt
    user_message: str           # initial user turn → PiMcpLoopInput.user_message
    toolset_name: str           # → PiMcpLoopInput.toolset_name
    result_schema: dict | None  # derived from AgentConfig.result_type; forwarded to piInference
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    max_iterations: int = 4
```

**`PiWorkerLoopResponse`** — typed wrapper around what `PiMcpLoopWorkflow` returns:

```python
@dataclass(slots=True, frozen=True)
class PiWorkerLoopResponse:
    result: Any      # instantiated result_type (or raw dict if result_type is None)
    raw: dict        # the unmodified dict returned by the workflow
    iterations: int
```

**`derive_result_schema(result_type: type | None) -> dict | None`**:

- `None` → return `None`.
- `pydantic.BaseModel` subclass → `result_type.model_json_schema()`.
- Python dataclass → `pydantic.TypeAdapter(result_type).json_schema()`.
- Anything else → raise `TypeError` with a clear message.

Returns a portable JSON Schema that crosses the Temporal polyglot boundary unchanged.

**`validate_and_coerce_output(raw: dict | str, result_type: type | None) -> Any`**:

- `result_type is None` → return `raw` as-is.
- `raw` is a string → `json.loads`; raise `ValueError` on parse failure.
- Instantiate `result_type` from the parsed dict; raise `ValueError` on validation failure.
- Return the typed instance.

---

### 2. `PiMcpLoopInput` gains `result_schema` (`feedback/pi_mcp_workflow.py`)

```python
@dataclass
class PiMcpLoopInput:
    ...
    result_schema: dict | None = None   # new field; forwarded to piInference payload
```

The workflow passes `result_schema` verbatim into each `piInference` call:

```python
pi_payload = {
    "provider": ...,
    "messages": messages,
    "tools": tools,
    "resultSchema": input.result_schema,   # new key; TS ignores it if None/absent
}
```

No other change to the workflow loop.

---

### 3. TypeScript `piInference` validates its final output (`services/pi-worker/src/activities.ts`)

Add `resultSchema?: Record<string, unknown>` to `PiInferenceInput`.

On the final turn (when `toolCalls` is empty) and `resultSchema` is present:
- Parse `finalText` as JSON.
- Validate the parsed object against `resultSchema` (e.g. using `ajv` or `@sinclair/typebox`).
- If validation fails → `ApplicationFailure.nonRetryable` with type `PiOutputSchemaError`.

This lets the TS worker surface schema mismatches early and clearly. Python re-validates independently on its side.

---

### 4. Updated `Agent._create_pi_worker_dispatch_async` (`agent.py`)

Replace the current single-tool-call implementation with:

1. Call `derive_result_schema(self.config.result_type)` → `result_schema`.
2. Build `PiWorkerLoopRequest` from `AgentConfig` fields + `input_payload`.
3. Dispatch to `PiMcpLoopWorkflow` (via an injectable `_loop_runner` callable so Agent remains testable without Temporal).
4. Call `validate_and_coerce_output(workflow_output.final_text, self.config.result_type)`.
5. Return a `PiWorkerLoopResponse`.

The existing toolset guard (exactly one toolset required) is kept unchanged.

---

## Data Flow

```
AgentConfig(execution_backend="pi_worker", toolset_name="X", result_type=MyModel)
  │
  ├─ derive_result_schema(MyModel) → JSON Schema dict
  │
  ├─ PiWorkerLoopRequest { instructions, user_message, toolset_name, result_schema, ... }
  │
  └─ _loop_runner(request) → invokes PiMcpLoopWorkflow (Temporal)
       │
       ├─ agents.mcp.list_pi_tools("X") → tool schemas
       ├─ piInference(tools, messages, resultSchema) → { toolCalls: [...] }
       ├─ agents.mcp.call_pi_tool(...) per tool call   ← loop managed by PiMcpLoopWorkflow
       ├─ piInference(updated messages, resultSchema) → { finalText: '{"field":"v"}', toolCalls: [] }
       │     └─ [TS] validates finalText against resultSchema → OK
       └─ PiMcpLoopOutput { final_text: '{"field":"v"}', iterations: 2 }
  │
  └─ validate_and_coerce_output(final_text, MyModel)
       → json.loads → MyModel(field="v")
  │
  └─ PiWorkerLoopResponse { result: MyModel(field="v"), raw: {...}, iterations: 2 }
```

---

## Boundary Validation

| Boundary | Validated | Error |
|----------|-----------|-------|
| `derive_result_schema` | `result_type` is BaseModel / dataclass / None | `TypeError` |
| `PiWorkerLoopRequest` | exactly one toolset configured | `ValueError` |
| TypeScript `piInference` (final turn) | `finalText` JSON-parses and matches `resultSchema` | `ApplicationFailure.nonRetryable` |
| `validate_and_coerce_output` | output round-trips to `result_type` | `ValueError` |

---

## Files Touched

| File | Change |
|------|--------|
| `agents/tools/mcp/pi_loop_contract.py` | **New** — `PiWorkerLoopRequest`, `PiWorkerLoopResponse`, `derive_result_schema`, `validate_and_coerce_output` |
| `agent.py` | Replace `_create_pi_worker_dispatch_async` body; inject `_loop_runner` |
| `examples/feedback_demo/feedback/pi_mcp_workflow.py` | Add `result_schema` to `PiMcpLoopInput`; forward to `piInference` payload |
| `services/pi-worker/src/activities.ts` | Add `resultSchema?` to `PiInferenceInput`; validate on final turn |
| `examples/feedback_demo/run_pi_mcp_loop_e2e.py` | Extend to pass `result_type`; assert typed round-trip and invalid-output error |
| `tests/unit/test_agent.py` | Unit tests for `derive_result_schema` and `validate_and_coerce_output` |
| `agents/tools/mcp/__init__.py` | Re-export new contract symbols |

---

## E2E Validation Path

`run_pi_mcp_loop_e2e.py` already stubs `piInference` so the test runs without the TS worker or LLM keys. The extension for this ticket:

- Define `MyEchoResult(BaseModel)` with a required field.
- Pass `result_type=MyEchoResult` into `AgentConfig`.
- Fake `piInference` returns `finalText='{"echo": "pi-mcp-loop"}'` on the final turn.
- Assert the returned value is `MyEchoResult(echo="pi-mcp-loop")`.
- Second case: fake returns malformed JSON → assert `ValueError` at the Python boundary.

---

## Out of Scope

- Any change to the pydantic_ai path.
- Multi-toolset pi_worker support.
- Streaming or partial results.
- Changing the loop iteration logic in `PiMcpLoopWorkflow`.
