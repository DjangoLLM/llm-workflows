# Phase 3: Implement typed Rust agents, tools, and managed inference

CODING-2068 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

Removing Pydantic AI also removes typed result validation, multi-turn tool execution, and validation feedback. A raw model call is insufficient to replace the existing Agent contract.

## Solution

Implement a Rust-owned agent loop with one native provider, schema-checked Rust tools, bounded repair, and managed SQLite persistence. Its turn boundaries are reusable by Temporal without replaying the entire agent conversation.

## User stories

1. As an agent author, I want to supply instructions and structured input, so that the provider receives the intended task.
2. As a caller, I want to declare a Rust result type, so that successful output has a checked shape.
3. As a tool author, I want to publish the same schema used for validation, so that advertised and actual inputs agree.
4. As a caller, I want to receive nested values and nullable fields, so that ordinary structured decisions fit.
5. As an agent author, I want to allow a specific tool set, so that the model cannot invoke unrelated tools.
6. As an operator, I want to bound turns and execution time, so that a run cannot continue indefinitely.
7. As a caller, I want to cancel in-flight work, so that abandoned requests release local resources.
8. As an agent author, I want to receive validation feedback, so that the model can correct a malformed result.
9. As an operator, I want to inspect safe failure records, so that diagnostics do not leak credentials.
10. As a maintainer, I want to exercise real inference and deterministic failures, so that acceptance covers transport and edge cases.

## Implementation decisions

1. Implement a direct Rust HTTP adapter for OpenAI Responses with explicit model, instructions, structured input, timeout, output schema, and permitted function tools. Read credentials from runtime configuration. Disable unrequested hosted tools and provider conversation persistence where supported; retain the local transcript needed for continuation.

2. Use one schema source derived from Rust contract types plus explicit validation metadata. Maintain the bounded subset from Phase 1. Normalize only representational details accepted by the provider; reject unsupported constraints and ambiguous optional/default behavior before making a request.

3. On the wire, fixed object fields are required; optional Rust values appear explicitly as null. Disallow extra object fields. Validate final JSON against the declared schema and deserialize it into the Rust result type. Custom domain validation runs before managed success. Ledger JSON is the validated value, not a response string.

4. Drive the pure transition function with a provider-turn result containing function calls, final output, refusal, or provider failure. Preserve instructions, tool call identifiers, ordering, and any provider continuation items required by the supported response contract. Never search commentary for a usable JSON fragment.

5. Execute tool calls serially in provider order in this release. Validate arguments before invocation and results before returning them to the provider. Unknown tools and forbidden registrations fail without invoking code. Metadata includes exposure permission and read-only/idempotent/non-idempotent effect classification.

6. Bound each run by a configured total deadline, provider-call deadline, tool deadline, maximum provider turns, and maximum validation repairs. Defaults are 300 seconds total, 60 seconds per provider call/tool, 16 provider turns, and 2 validation repairs. Validate positive finite values. A repair consumes a turn and does not reset the deadline.

7. Surface refusal and incomplete provider responses as distinct failures. Validation repair feeds a safe structured error back through the loop. Do not automatically retry side-effecting tool actions. Transport retry is owned explicitly by the caller/orchestrator; the adapter has no hidden request-retry loop.

8. Cancellation stops waiting and cancels owned HTTP futures/tasks. A tool must support cooperative cancellation or declare that remote completion is uncertain. Do not report that cancelling a local future reverses an external effect.

9. Persist the managed invocation and its terminal typed outcome through Phase 2. Phase 3's direct loop is a non-durable convenience path; only read-only/idempotent tools belong in its acceptance example. Durable effect recovery is delivered by Phases 4 and 5.

10. Expose the provider-turn and tool-dispatch operations for the Temporal adapter, keeping the same transition and validation logic. Do not add a second agent implementation or run Python, Node, or a CLI to obtain results.

## Testing decisions

- Use the public managed-agent interface against a controllable HTTP provider fixture, with real Rust tools and real SQLite. Exercise nested success, tool call/result association, schema rejection before HTTP, malformed output followed by repair, and exhausted repair.

- Test instruction preservation, defaults/nullability, extra fields, tool-name authorization, invalid tool output, refusal/incomplete responses, total deadlines, cancellation, and safe persisted errors.

- Run a real provider acceptance case with an explicitly recorded model: a nested result with an integer, enum, array, and nullable field, plus a separate read-only tool round trip. Missing credentials make live acceptance incomplete rather than a passing mock.

- Prior art: existing Agent/ManagedAgent public tests, tool schema tests, and live inference tests. The fake boundary is HTTP, not a new production injection API for every private helper.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

Other providers, model benchmarking, CLI backends, Python result compatibility, public streaming, parallel tool execution, automatic unsafe tool retries, and MCP transport.

## Further notes

Depends on: CODING-2066, CODING-2067. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

Provider contract sources: [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [function calling](https://developers.openai.com/api/docs/guides/function-calling). These establish provider mechanisms; the limits and error policy above are project decisions.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

