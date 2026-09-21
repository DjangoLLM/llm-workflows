# freedom-agents framework review

Date: 2026-09-21  
Reviewed commit: `11862bdc4d8b7f69e3c89907a00a9c7ffa103ce7`  
Scope: the current `freedom-agents` framework, including typed LLM steps, pipeline bookkeeping, tools, and Temporal execution. This is a whole-package review, not a commit diff.

Eight issues were reproduced. No implementation changes were made during the review. Source paths below are relative to the package root; line numbers refer to the reviewed commit.

## 1. P1: Agent instructions disappear on pi-worker

Location: [`core/tools/mcp/pi_model.py`](../../core/tools/mcp/pi_model.py), line 153.

The payload translator collects `SystemPromptPart` content but ignores `ModelRequest.instructions`, where Pydantic AI carries the instructions supplied by `AgentConfig`. The pi-worker therefore receives no configured instructions on this path.

Reproduction: construct an `Agent` with `execution_backend="pi_worker"`, instructions `Always speak French`, and an injected fake Temporal client. Run the agent and inspect the workflow payload. `systemPrompt` is an empty string.

Suggested fix: use the existing model instruction-extraction helper and preserve explicit system prompts. Add a test through the real Pydantic AI agent graph that asserts the outgoing instructions.

## 2. P1: Default queue routing leaves inference waiting

Location: [`core/tools/mcp/pi_model.py`](../../core/tools/mcp/pi_model.py), line 66; [`management/commands/run_temporal_worker.py`](../../management/commands/run_temporal_worker.py).

The model resolves `AGENTS_PI_WORKER_HOST_TASK_QUEUE`, then `AGENTS_TEMPORAL_TASK_QUEUE`, then defaults to `agents`. The bundled worker instead reads `TEMPORAL_TASK_QUEUE`, defaulting to `ai-pipeline-queue`. Without an explicit routing override or another worker, the inference workflow is submitted to a queue the bundled worker does not poll.

Reproduction: configure only `TEMPORAL_TASK_QUEUE="ai-pipeline-queue"`. `_default_task_queue()` returns `agents`.

Suggested fix: keep the explicit pi-worker host override, then fall back to the same setting and default used by the bundled worker. Test default and overridden routing together.

## 3. P1: The reusable app cannot migrate independently

Locations:

- [`migrations/0005_interpretationrun_interpretationsegment.py`](../../migrations/0005_interpretationrun_interpretationsegment.py), line 10, depends on `transcripts`.
- [`migrations/0012_rename_module_name_proposedmodule_name_and_more.py`](../../migrations/0012_rename_module_name_proposedmodule_name_and_more.py), depends on `plane_agent`.
- [`migrations/0017_move_interpretation_models_to_personal.py`](../../migrations/0017_move_interpretation_models_to_personal.py), depends on `personal`.

The migration graph still requires host-specific applications even though the current framework models do not. A consumer following the standalone installation instructions cannot load the graph with only `agents` installed. The test settings disable agents migrations, so those tests do not exercise this installation boundary.

Reproduction: configure Django with `INSTALLED_APPS=["agents"]` and construct `MigrationLoader(None)`. It raises `NodeNotFoundError` for the missing `transcripts.0001_initial` dependency.

Suggested fix: provide a standalone migration path while preserving an upgrade path for existing installations. Add a migration-graph test with only the documented package dependencies installed.

## 4. P2: Structured-output retries crash

Location: [`core/tools/mcp/pi_model.py`](../../core/tools/mcp/pi_model.py), line 178.

When structured output fails validation, Pydantic AI sends a `RetryPromptPart` to let the model correct its response. The translator does not support this part and raises `NotImplementedError`, preventing the normal retry.

Reproduction: use a result model with an integer `count` field. Have the fake Temporal client return an output-tool call containing `{"count": "bad"}`, followed by a valid result if called again. The run raises `NotImplementedError` for `RetryPromptPart` after exactly one inference call.

Suggested fix: translate validation feedback, including its tool-call association where present. Test malformed output followed by a valid correction through the agent graph.

## 5. P2: Preprocessing failures remain PENDING

Location: [`core/pipeline_structure.py`](../../core/pipeline_structure.py), line 249.

`PipelineStep.run()` invokes `pre_execute()` before entering its failure handler. If preprocessing raises, the eagerly created step row remains `PENDING`, with no error or terminal timestamp.

Reproduction: create a step whose `pre_execute()` raises `ValueError("bad input")`, then call `run()`. The exception propagates, but the persisted row remains `PENDING` and `error_message` is `None`.

Suggested fix: include preprocessing in the tracked execution lifecycle. Test that a preprocessing exception produces a failed step with the original error recorded.

## 6. P2: Parent lineage is silently discarded

Location: [`core/pipeline_structure.py`](../../core/pipeline_structure.py), line 68.

The runtime accepts and stores `parent_ids` on the Python instance but never writes them to the `PipelineStep.parents` relationship. Callers can supply lineage successfully while the database loses it.

Reproduction: execute a parent step, then execute a child with `parent_ids=[parent_step_id]`. The child's persisted `parents.count()` is zero.

Suggested fix: persist the supplied relationships when creating the step and validate that they belong to the intended run. Test the stored relationship after execution.

## 7. P2: Duplicate serializers disagree on UUIDs

Location: [`core/pipeline_structure.py`](../../core/pipeline_structure.py), line 15; compare [`core/agent.py`](../../core/agent.py), line 29.

The pipeline JSON conversion helper omits UUID handling that the near-duplicate agent helper provides. A successful code step returning a UUID fails while saving its output and is marked failed.

Reproduction: return `{"id": uuid.uuid4()}` from a code step. `run()` raises `TypeError: Object of type UUID is not JSON serializable`; the step ledger records `FAILED`.

Suggested fix: consolidate serialization through one shared conversion, preferably the existing Pydantic serialization facilities. Test UUIDs nested in mappings and typed outputs.

## 8. P2: Tool adapters lose schema semantics

Locations: [`core/tools/pydantic_ai_adapter.py`](../../core/tools/pydantic_ai_adapter.py), line 31; [`core/tools/mcp/adapter.py`](../../core/tools/mcp/adapter.py).

Both adapters rebuild signatures from bare field annotations and literal defaults. This drops field constraints and descriptions and treats fields with `default_factory` as required. The schema advertised to callers therefore differs from the input model used during execution.

Reproduction: adapt an input model containing `count: int = Field(ge=1, description="Positive count")` and `tags: list[str] = Field(default_factory=list)`. Pydantic AI's generated tool schema loses the count minimum and description and lists both `count` and `tags` as required. The original model requires only `count`. The MCP adapter repeats the same signature-building logic.

Suggested fix: preserve the input model's schema and validation metadata through supported adapter facilities, and share the conversion between adapters. Test constraints, descriptions, and factory defaults in the exposed schemas.

## Verification and limits

- Used the existing review environment with Python 3.12.12, Django 4.2.27, and the pinned Pydantic AI 1.34.0.
- Exercised agent translation with the real Pydantic AI graph and injected fake Temporal clients. No live inference calls were made.
- Exercised pipeline bookkeeping against an in-memory SQLite database with tables created from the current models.
- Checked standalone migration loading separately, without disabling migrations.
- Compared the original Pydantic input schema with the generated Pydantic AI tool schema.
- The full PostgreSQL/Temporal suite was not run. Queue mismatch was verified through configuration resolution, not a live stalled workflow. MCP schema behavior was identified from the duplicate implementation; its transport was not exercised.
