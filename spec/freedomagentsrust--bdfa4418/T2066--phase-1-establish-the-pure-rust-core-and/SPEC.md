# Phase 1: Establish the pure Rust core and execution contracts

CODING-2066 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

The existing execution package depends on Django, Python objects, and process-global registration. Rust consumers need a reusable, headless entry point before persistence and inference can be ported.

## Solution

Create an executable Rust foundation with stable typed contracts and one deterministic code-step example. It defines the vocabulary later phases implement without bringing in a desktop shell or an interpreter.

## User stories

1. As an application author, I want to run a code step from a Rust program, so that I can adopt the core without a UI.
2. As a pipeline author, I want to separate bookkeeping from orchestration, so that workflow policy has one owner.
3. As an agent author, I want to declare a result contract, so that invalid output cannot become a branch decision.
4. As a tool author, I want to declare typed arguments and outcomes, so that calls can be checked before execution.
5. As an operator, I want to supply explicit runtime configuration, so that startup does not depend on Django settings.
6. As a consumer, I want to receive stable run and step identifiers, so that I can correlate later results.
7. As a maintainer, I want to reject duplicate registrations at startup, so that dispatch is unambiguous.
8. As a consumer, I want to receive classified errors, so that I can distinguish retryable failures from bad input.
9. As a framework maintainer, I want to inject effects through supported capabilities, so that Modules stay composable.
10. As a maintainer, I want to compile a separate consumer and inspect dependencies, so that the public package works without Python or Node.

## Implementation decisions

1. Establish a Rust workspace for the new runtime in the FreedomAgentsRust module's configured repository. Record the actual implementation root and source/framework revisions before code changes. Do not overwrite the existing Django repository or assume the supplied framework worktree is the new application's repository.

2. Use small Rust library boundaries for execution contracts, execution services, SQLite integration, provider integration, and Temporal hosting. Phase 1 implements only what its runnable example needs. The public core must not depend on Tauri, a webview, React, Python, or a JavaScript runtime.

3. Define a PipelineRun as one requested workflow execution, a PipelineStep as one logical step occurrence, a StepAttempt as one physical execution attempt, and an AgentRun as one managed agent invocation. Step keys identify registered behavior; occurrence keys identify repeated use of that behavior within a run. A retry preserves occurrence identity.

4. Use opaque UUID identities represented as canonical strings at serialized boundaries. Structured payloads are JSON values with a versioned envelope. Workflow entry and activity result contracts that require objects reject scalar roots and JSON encoded inside strings. Arbitrary ledger JSON remains possible.

5. Expose asynchronous Rust execution as the primary interface. The standalone example owns its async runtime; library callers supply an existing runtime. Do not embed nested runtimes or reproduce Python synchronous/thread-spawning convenience behavior.

6. Provide immutable startup registrations for pipeline definitions, code steps, tools, and agent configurations. Reject duplicate stable names and unresolved references before accepting work. Definitions carry explicit schema/behavior versions; no dotted-path imports, dynamic code loading, or user-supplied executable text.

7. Separate a provider-turn contract, a tool-execution contract, and a pure agent-loop transition function. The same transition logic can be driven in memory in Phase 3 and from Temporal-recorded results in Phase 4. The loop itself performs no network, clock, random, or database calls.

8. Define errors with a stable category, safe message, retryability, and optional internal cause. Categories include configuration, contract validation, provider, tool, persistence, timeout, cancellation, and conflict. Secrets are runtime-only; configuration snapshots store redacted settings and definition versions.

9. Choose direct OpenAI Responses HTTP integration from Rust as the first provider, matching the existing direct-provider direction. Require an explicit model configuration; no claim of access to a particular model. CLI backends and additional providers are deferred. Rust schema generation and validation must reject unsupported constructs instead of weakening them.

10. Agree on bounded object schemas for agent/tool contracts: fixed objects, nested objects, arrays, strings, finite numbers, booleans, enums, and explicit nullable fields. Reject recursion, arbitrary object keys, ambiguous unions, and unsupported constraints before inference. Exact schema normalization belongs to Phase 3.

11. Keep framework-owned generated Models and generic execution request/result contracts distinct. A request DTO is not a handwritten copy of a generated entity. Background services receive supported Store/execution capabilities independently of GraphQL request context; any new host primitive needs its own executable proof.

## Testing decisions

- Use the public Rust entry point from a separate minimal consumer to run a code step and assert typed output and stable error categories. This is the primary behavioral boundary.

- Round-trip public envelopes and reject wrong versions, scalar activity payloads, invalid configuration, duplicate keys, and unresolved registrations. Tests assert observable errors rather than private registry layout.

- Run Cargo build/test with Python and Node unavailable at runtime. Inspect resolved runtime dependencies for accidental desktop or interpreter dependencies.

- Prior art: current Agent construction, catalog validation, boot-gate, and public module-export tests. Port their intended behavior, not Python implementation details.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

Persistence, real inference, Temporal execution, GraphQL/MCP exposure, UI, database alternatives, Python API compatibility, and broad provider parity.

## Further notes

Depends on: none. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

