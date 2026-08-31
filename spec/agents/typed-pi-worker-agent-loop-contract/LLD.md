# LLD: Typed pi-worker Agent Loop Contract

**Ticket:** #432 · `010649cd-9c09-464a-b69d-7a580e647410`
**Module:** `freedom-agents`
**Phase:** LLD

---

## Design principle: diverge as late as possible

The pi-worker backend differs from the OpenAI backend only in **where the LLM call goes**. Everything else — message construction, tool calling, multi-turn loop, structured-output coercion, validation, tool dispatch — is already implemented by `pydantic_ai`. Therefore the divergence point is the `pydantic_ai.models.Model.request()` boundary (`.venv/.../pydantic_ai/models/__init__.py:586`).

For `execution_backend="pi_worker"` we construct a `pydantic_ai.Agent` **exactly like** the OpenAI path. We swap only the `Model` instance. Tools are resolved from `default_registry` via the existing `build_pydantic_ai_tool` adapter — the same code path the OpenAI backend already uses (`core/agent.py:128-133`). pydantic_ai owns the full agent graph for both backends:

- looping on tool calls,
- invoking function tools directly (in-process Python calls),
- deriving the JSON Schema from `output_type` (`AgentConfig.result_type`),
- validating + coercing the final structured output into a typed instance.

### Why the MCP layer is no longer on this path

Because pydantic_ai owns tool dispatch and the function tools live in this repo's `default_registry`, the previous MCP detour (Python → `PiMcpBridge` → STDIO subprocess → MCP server → same Python registry) is a round-trip with no functional purpose. We will drop MCP from the agent path entirely in this ticket. `PiMcpBridge`, `agents.tools.mcp.server`, and the `agents.mcp.list_pi_tools` / `agents.mcp.call_pi_tool` Temporal activities remain in the repo for non-agent use and for the standalone `PiMcpLoopWorkflow` demo, but neither the `pydantic_ai` nor the `pi_worker` agent path imports them.

A separate follow-up story will track full removal / consolidation of the MCP layer — see "Follow-ups" at the end of this document.

---

## Architectural shifts vs prior LLD

| Concern | Prior LLD | This LLD |
|--------|-----------|----------|
| Output schema derivation | New `derive_result_schema` helper | pydantic_ai derives it from `output_type` |
| Output validation | New `validate_and_coerce_output` helper | pydantic_ai validates via `output_object`/`output_tools` |
| Multi-turn loop | `PiMcpLoopWorkflow` (Temporal) drives it | pydantic_ai's `_agent_graph` drives it |
| Tool invocation | Temporal activities + `PiMcpBridge` | `default_registry` tool functions called in-process by pydantic_ai |
| Tool discovery for the agent | MCP subprocess (`list_pi_tools`) | `default_registry.resolve_toolset(name)` |
| TS-side schema validation | New `ajv` validation in `piInference` | Not added — pydantic_ai validates on Python side |
| Per-run Temporal surface | `PiMcpLoopWorkflow` (long, multi-activity) | `PiInferenceTurnWorkflow` (1 activity, per inference turn) |
| `_create_pi_worker_dispatch_async` | Rewritten | Deleted |
| `_pi_worker_dispatch` / `_pi_worker_dispatch_async` attributes | Kept | Deleted |
| `Agent.run` / `run_sync` branching | Two paths | Single path through `self._pydantic_agent` |

---

## Files Touched

| File | Kind | Why |
|------|------|-----|
| `core/tools/mcp/pi_model.py` | **New** | `PiWorkerModel(pydantic_ai.models.Model)` — single-turn inference dispatcher |
| `core/temporal/workflows.py` | Modified | Add `PiInferenceTurnWorkflow` (single-activity, no loop) |
| `core/agent.py` | Modified | Branch model construction in `_create_pydantic_agent`; delete `_pi_worker_dispatch*`; collapse `run`/`run_sync` to one path; simplify `ManagedAgent` |
| `services/pi-worker/src/activities.ts` | Modified | Accept optional `outputObject?` (name + jsonSchema) to bias structured output; no validation step |
| `examples/feedback_demo/run_pi_mcp_loop_e2e.py` | Modified | Drive a real pydantic_ai `Agent` whose model is `PiWorkerModel`; tools come from `default_registry`; stubbed `piInference` returns tool_call then structured final output; assert typed `agent_run.output` |
| `tests/unit/test_agent.py` | Modified | Replace pi_worker-specific tests; add `PiWorkerModel.request` unit tests |
| `core/tools/mcp/__init__.py` | Modified | Re-export `PiWorkerModel` |

No new module for MCP bridging. No migrations. No settings changes. No new Python dependencies.

---

## Step 1 — `PiWorkerModel` (new)

File: `core/tools/mcp/pi_model.py`.

### 1a. Class shape

- Subclass `pydantic_ai.models.Model`.
- Constructor accepts: `provider: str`, `model_name: str`, `temporal_client_factory: Callable[[], Awaitable[Client]] | None = None`, `task_queue: str | None = None` (the host Temporal task queue on which `PiInferenceTurnWorkflow` runs; defaults from Django settings).
- The factory is injectable so unit tests can avoid a real Temporal connection.

### 1b. Required overrides

- `@property def model_name(self) -> str` → returns `self._model_name`.
- `@property def system(self) -> str` → returns `"pi_worker"` (used by pydantic_ai for instrumentation).

### 1c. `async def request(self, messages, model_settings, model_request_parameters) -> ModelResponse`

Steps inside `request`:

1. Call `self.prepare_request(model_settings, model_request_parameters)` first (pydantic_ai's recommended pattern at `models/__init__.py:645`).
2. **Translate `messages` to pi_payload messages.** Iterate `messages: list[ModelMessage]`:
   - `ModelRequest` parts of type `SystemPromptPart` → `{"role": "system", "content": part.content}`.
   - `ModelRequest` parts of type `UserPromptPart` with `str` content → `{"role": "user", "content": part.content}`.
   - `ModelResponse` parts of type `TextPart` → `{"role": "assistant", "content": part.content}`.
   - `ModelResponse` parts of type `ToolCallPart` → `{"role": "assistant", "content": json.dumps({"tool_call": part.tool_name, "args": part.args_as_json_str() or "{}"})}`. The pi-worker's `PiInferenceMessage` schema is plain text only; we encode tool-call structure into the assistant text turn, identical to how `PiMcpLoopWorkflow` does it today (`pi_mcp_workflow.py:163-176`).
   - `ModelRequest` parts of type `ToolReturnPart` → `{"role": "user", "content": f"<tool_result>{json.dumps({...})}</tool_result>"}`.
   - Any other part kind: raise `NotImplementedError("PiWorkerModel does not yet support <kind>")`. Image, audio, builtin tool parts are out of scope.

3. **Translate tools.** From `model_request_parameters.function_tools: list[ToolDefinition]`: build a list of `{"name": td.name, "description": td.description, "input_schema": td.parameters_json_schema}`. This is the pi-worker tool shape `piInference` already expects.
4. **Translate output schema.** Three cases on `model_request_parameters.output_mode`:
   - `"text"` (default — no `output_type` set) → omit `outputObject` from the payload.
   - `"tool"` (pydantic_ai's default for structured `output_type`) → append `model_request_parameters.output_tools` to the tools list. pydantic_ai will validate the resulting tool call against its registered output tool.
   - `"native_output"` or `"prompted"` → build `outputObject = {"name": output_object.name, "description": output_object.description, "jsonSchema": output_object.json_schema}` and include it in the payload.
5. **Dispatch via Temporal.** Acquire client via `self._temporal_client_factory()`. Start `PiInferenceTurnWorkflow` with the assembled input dict; await its result. Workflow id: `f"pi-inference-{uuid.uuid4().hex[:12]}"`. Task queue: from constructor (`self._task_queue`).
6. **Translate the response.** Workflow returns a dict `{"finalText": str, "toolCalls": list, "usage": {...}}`. Build a `ModelResponse`:
   - If `toolCalls` is non-empty: parts = `[ToolCallPart(tool_name=c["name"], args=c.get("arguments", {}), tool_call_id=c.get("id") or _new_id()) for c in toolCalls]`. Also prepend a `TextPart(content=finalText)` iff `finalText` is non-empty.
   - Else: parts = `[TextPart(content=finalText)]`.
   - Set `usage = RequestUsage(input_tokens=..., output_tokens=..., total_tokens=...)` from the `usage` dict.
   - Return `ModelResponse(parts=parts, model_name=self.model_name, usage=usage)`.

### 1d. Streaming

Do not implement `request_stream`. Inherit the base-class `NotImplementedError`. Out of scope.

### 1e. Errors

- Temporal connection errors propagate.
- Pi-worker `ApplicationFailure` propagates as `temporalio.exceptions.ApplicationError`.
- pydantic_ai validates the final structured output against `output_type`; on mismatch it raises `pydantic_ai.exceptions.UnexpectedModelBehavior` (or invokes `ModelRetry`). That is the boundary error surface we want.

### 1f. Critically: tools are not invoked here

`PiWorkerModel.request()` reports the LLM's tool-call *intent* by returning `ToolCallPart`s. It never calls a tool. pydantic_ai's agent graph receives the `ModelResponse`, looks up the named tool in its registered function-tool table, invokes it (Python in-process), wraps the return value in a `ToolReturnPart`, and calls `Model.request()` again. The Model is purely an I/O translator for inference.

---

## Step 2 — `PiInferenceTurnWorkflow` (new)

File: `core/temporal/workflows.py`.

### 2a. Why a workflow at all

`piInference` is a Temporal activity hosted by the TypeScript worker on `pi-inference-queue`. Activities cannot be invoked directly by a client — they must run inside a workflow. We define the smallest possible workflow: schedule one activity, return its result.

### 2b. Shape

- `@workflow.defn(name="agents.PiInferenceTurnWorkflow")`.
- Input: a single `dict` (the pi_payload assembled by `PiWorkerModel.request`).
- Method `run(self, payload: dict) -> dict`:
  1. `start_to_close_timeout = timedelta(seconds=payload.pop("activity_timeout_seconds", 60))`.
  2. `result = await workflow.execute_activity(pi_inference_stub, payload, task_queue="pi-inference-queue", start_to_close_timeout=timeout)`.
  3. `return result`.

### 2c. Activity stub

Move `pi_inference_stub` from `examples/feedback_demo/feedback/pi_mcp_workflow.py:38-46` to `core/temporal/activities.py` so it is no longer demo-scoped. Re-import it from the demo file to keep the standalone demo intact. The stub raises `NotImplementedError` — only its `@activity.defn(name="piInference")` registration matters; the real implementation is the TS worker.

### 2d. Worker registration

The host project's existing Temporal worker plugin (`core/temporal/worker_plugins.py`) already registers `core/temporal/workflows.py` workflows. Add `PiInferenceTurnWorkflow` to that registration list. No new plugin needed.

### 2e. Task queue

`PiInferenceTurnWorkflow` runs on the **host project's** primary task queue (whatever the agents worker is on); only the inner activity is routed to `pi-inference-queue`. Document this in the workflow docstring.

---

## Step 3 — Collapse `Agent` (modified)

File: `core/agent.py`.

### 3a. Delete

- `Agent._create_pi_worker_dispatch_async` (lines 145-190).
- `Agent._pi_worker_dispatch_async` and `Agent._pi_worker_dispatch` attribute assignments (lines 104-111).
- The branching in `Agent.run` / `Agent.run_sync` (lines 198-201, 211-214). Both methods now unconditionally call `self._pydantic_agent.run` / `.run_sync`.
- `ManagedAgent._pi_worker_dispatch` attribute (lines 237-241) and the `if self._pi_worker_dispatch is not None` branch in `_execute_run` (lines 328-331). The remaining code path (`self._agent.run_sync(input_payload)` + `_json_safe_value`) covers both backends.

### 3b. Modify `_create_pydantic_agent`

Branch on `config.execution_backend` to choose the model *only*:

- `"pydantic_ai"` (default) → existing OpenAI logic unchanged.
- `"pi_worker"` →
  - `model = PiWorkerModel(provider=..., model_name=str(config.model) if config.model else "gpt-4o-mini")`. `provider` is read from `config.extra_kwargs.get("provider", "openai")` if present, else `"openai"`.

Everything else inside `_create_pydantic_agent` is **shared by both backends**:

- `model_settings` (only applied when the model is an OpenAI variant; `PiWorkerModel` ignores it via the standard `Model.settings` machinery).
- `tools = list(config.tools or [])`.
- `if config.toolsets: for name in config.toolsets: for tool in default_registry.resolve_toolset(name): tools.append(build_pydantic_ai_tool(tool))`. **Identical for both backends.** This is the line that closes the MCP question — tools come from the in-repo registry on every path.
- `agent_kwargs` assembly (instructions, `output_type=config.result_type`, `tools=all_tools`, `extra_kwargs`).
- `return PydanticAgent(model=model, model_settings=model_settings, **agent_kwargs)`.

### 3c. Toolset count guard

The existing pi_worker requirement of "exactly one toolset" was specific to MCP (one bridge per agent). With registry-backed tools that constraint disappears. The guard can be relaxed for pi_worker — the same multi-toolset behavior the OpenAI path already supports.

Decision: drop the pi_worker single-toolset guard. Both backends accept zero, one, or many toolsets uniformly. This also simplifies the existing `__post_init__` / construction logic.

### 3d. Result

`Agent(pi_worker)` and `Agent(pydantic_ai)` differ in exactly one expression: which `Model` was constructed. Everything else — tool wiring, instructions, output_type, run/run_sync, ManagedAgent, persistence, signals — is one code path.

---

## Step 4 — TS `piInference` (modified)

File: `services/pi-worker/src/activities.ts`.

### 4a. Add optional structured-output input

- Add `outputObject?: { name: string; description?: string; jsonSchema: Record<string, unknown> }` to `PiInferenceInput`.
- When present, ask the provider for structured output using its native JSON-mode equivalent. On OpenAI: `response_format: { type: "json_schema", json_schema: outputObject }`.

### 4b. No validation

- pydantic_ai validates output on the Python side via `output_type` and triggers `ModelRetry` if structured output is malformed. The TS worker does not validate.

### 4c. Backwards compatibility

- Existing callers (which don't pass `outputObject`) keep working unchanged.

---

## Step 5 — E2E (modified)

File: `examples/feedback_demo/run_pi_mcp_loop_e2e.py`.

### 5a. Goal

Prove end-to-end that an `Agent(pi_worker, result_type=EchoSummary, toolsets=["echo"])` drives pydantic_ai's loop with our `PiWorkerModel`, that tools come from `default_registry`, and that the typed output round-trips.

### 5b. Tooling

Register an `"echo"` toolset in `default_registry` for the demo (or reuse if already present). The tool is a plain Python function: `def echo(text: str) -> dict: return {"echoed": text, "char_count": len(text)}`. No MCP subprocess involved.

### 5c. Wiring

1. Define `EchoSummary(BaseModel)` with one required field `summary: str`, used as `result_type`.
2. Register a local fake `piInference` activity (already in this file) with a 2-step script:
   - Turn 1: returns `toolCalls=[{"name":"echo","arguments":{"text":"pi-mcp-loop"}}]`, `finalText=""`.
   - Turn 2: returns `toolCalls=[]` and a structured final-result emission. Format matches whatever `output_mode` pydantic_ai picked (likely `"tool"` with a `final_result` tool call).
3. Register `PiInferenceTurnWorkflow` on the same Temporal worker.
4. Run `Agent(config=AgentConfig(execution_backend="pi_worker", instructions="...", toolsets=["echo"], result_type=EchoSummary))`. Call `agent.run_sync({"user_message": "Echo and summarize."})`.
5. Assert: `agent_run_result.output == EchoSummary(summary="echo confirmed")` (or whatever the fake's final turn emits).
6. Assert: the echo tool was called in-process (assert via a sentinel/counter on the registered function — no subprocess, no MCP).

### 5d. Negative case

Reset the script so the final turn emits a malformed structured payload. Assert `agent.run_sync(...)` raises `pydantic_ai.exceptions.UnexpectedModelBehavior`.

### 5e. PiMcpLoopWorkflow demo

The previous version of this file ran `PiMcpLoopWorkflow` directly. Move that coverage to a sibling script `run_pi_mcp_loop_workflow_demo.py` so the standalone-loop demo is not lost. It is no longer the path the agent uses.

---

## Step 6 — Unit tests (modified)

File: `tests/unit/test_agent.py`.

Remove `test_agent_run_sync_uses_pi_worker_bridge` and any other pi_worker-bridge-coupled tests. Add:

### 6a. `test_pi_worker_agent_constructs_with_pi_worker_model`

- `_patch_openai_model_construction(monkeypatch)`.
- Construct `Agent(config=AgentConfig(instructions="x", execution_backend="pi_worker", toolsets=[], result_type=None))`.
- Assert `isinstance(agent._pydantic_agent.model, PiWorkerModel)`.

### 6b. `test_pi_worker_agent_shares_registry_toolset_with_openai_path`

- Register a one-tool toolset under name `"_test_set"` in `default_registry` (or use an existing fixture).
- Build `Agent(pi_worker, toolsets=["_test_set"])`.
- Assert the resulting `_pydantic_agent`'s registered tools include the registry tool. Same assertion pattern as the existing OpenAI-path test (`test_agent_uses_explicit_config_with_string_model` or similar).

### 6c. `test_pi_worker_model_request_translates_text_response`

- Construct `PiWorkerModel(provider="stub", model_name="stub", temporal_client_factory=fake)` where the fake client's `execute_workflow` returns `{"finalText": "ok", "toolCalls": [], "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2}}`.
- Call `await model.request(messages=[ModelRequest(parts=[UserPromptPart("hi")])], model_settings=None, model_request_parameters=ModelRequestParameters())`.
- Assert returned `ModelResponse.parts == [TextPart(content="ok")]` and usage is populated.

### 6d. `test_pi_worker_model_request_translates_tool_call`

- Fake returns `{"finalText": "", "toolCalls": [{"name": "echo", "arguments": {"text": "x"}}], "usage": {...}}`.
- Assert returned `ModelResponse` contains a single `ToolCallPart(tool_name="echo", args={"text": "x"})`.

### 6e. `test_pi_worker_model_includes_output_object`

- `ModelRequestParameters(output_mode="native_output", output_object=OutputObjectDefinition(name="MyOut", json_schema={"type":"object","properties":{"x":{"type":"string"}}}))`.
- Use a recording fake client capturing `execute_workflow`'s payload.
- Assert captured payload contains `"outputObject"` with the expected name + jsonSchema.

### 6f. `test_pi_worker_model_includes_function_tool_schemas`

- `ModelRequestParameters(function_tools=[ToolDefinition(name="echo", description="...", parameters_json_schema={"type":"object"})])`.
- Assert captured `tools` list has one entry with `name="echo"` and the schema in `input_schema`.

### 6g. Existing `test_agent_config_*` tests

Remain unchanged.

---

## Boundary Validation Matrix

| Boundary | Where | Error |
|---------|-------|-------|
| `execution_backend` value | `AgentConfig.__post_init__` (existing) | `ValueError` |
| Toolset resolves in registry | `default_registry.resolve_toolset(name)` (existing) | `KeyError` |
| Unknown `ModelMessage` part kind | `PiWorkerModel.request` translation step | `NotImplementedError` |
| Output schema mismatch on final turn | pydantic_ai agent graph after `request` returns | `UnexpectedModelBehavior` / `ModelRetry` |
| Activity failure in pi-worker | Temporal `ApplicationFailure` propagates | `ApplicationError` |

All validation lives in pre-existing layers. The only new failure mode is `NotImplementedError` for unsupported message-part kinds — a programmer-facing error.

---

## Acceptance Checklist

1. `AgentConfig(execution_backend="pi_worker")` is accepted and validated — covered by #429.
2. `Agent` routes pi_worker through a `pydantic_ai.Agent` whose `Model` is `PiWorkerModel` rather than `OpenAIResponsesModel` — test 6a.
3. The pi-worker path uses `default_registry`-resolved tools, same as the OpenAI path — test 6b + E2E.
4. The pi-worker path returns a structured, typed output payload via pydantic_ai's `output_type` validator — E2E asserts `result.output == EchoSummary(...)`.
5. The pydantic_ai path is unchanged — pre-existing tests stay green.
6. Invalid input / output shapes raise clear errors at the boundary — pydantic_ai's output-validation surface + negative E2E case.
7. E2E validation exists — `run_pi_mcp_loop_e2e.py` exercises pydantic_ai + `PiWorkerModel` + registry-backed tool + real Temporal worker (with fake piInference).
8. Schema derived from `result_type` reaches the pi-worker — `PiWorkerModel.request` forwards `output_object.json_schema` into the payload; pydantic_ai derives it from `AgentConfig.result_type`.

---

## Follow-ups (new tickets to file)

These are out of scope here but enabled by this LLD.

1. **Remove the MCP layer from the agents codebase.** Since neither agent path uses `PiMcpBridge`, `agents.tools.mcp.server`, `agents.mcp.list_pi_tools`, `agents.mcp.call_pi_tool`, or `PiMcpLoopWorkflow`, they can be deleted along with their tests. Any consumer outside the agent path (currently: the `PiMcpLoopWorkflow` standalone demo) is the only blocker — relocate or drop the demo, then sweep the rest.
2. **Async `Agent.create()` factory** for callers already inside an event loop. Currently `Agent.__init__` is synchronous and assumes no running loop.
3. **Streaming support** in `PiWorkerModel.request_stream` once the TS worker exposes streaming inference.

---

## Out of Scope

- Streaming responses.
- Image / audio / builtin-tool message parts in `PiWorkerModel`.
- Removing or migrating `PiMcpLoopWorkflow` and other MCP code (separate follow-up ticket).
- Running pydantic_ai agents inside a Temporal workflow.
- Async `Agent` constructor for callers inside an existing event loop.
