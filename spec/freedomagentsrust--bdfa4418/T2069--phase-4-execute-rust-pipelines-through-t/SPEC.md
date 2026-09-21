# Phase 4: Execute Rust pipelines through Temporal

CODING-2069 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

The headless core needs durable execution order and recoverable progress. Running the full multi-turn agent as one retried activity would repeat completed tool work and obscure recovery boundaries.

## Solution

Provide a Rust Temporal worker and client that schedule code execution, individual inference turns, and individual tool calls as separate activities, using the shared core contracts and SQLite ledger.

## User stories

1. As an operator, I want to start one Rust worker, so that pipelines run without Django bootstrap.
2. As a caller, I want to submit a typed workflow request, so that execution has a stable identity.
3. As a workflow author, I want to mix code and agent steps, so that one workflow owns the order.
4. As an agent author, I want to record inference turns independently, so that replay reuses accepted model decisions.
5. As a tool author, I want to execute a tool in its own activity, so that retry policy matches the effect.
6. As an operator, I want to restart a worker, so that Temporal can resume recorded progress.
7. As a caller, I want to receive structured activity results, so that decoding does not fail on JSON strings.
8. As a maintainer, I want to reject invalid registrations before polling, so that bad deployments fail early.
9. As an operator, I want to stop a worker gracefully, so that owned activities can shut down predictably.
10. As a consumer, I want to inspect the ledger alongside workflow state, so that execution remains auditable.

## Implementation decisions

1. Integrate an exact, tested Temporal Rust SDK version compatible with the selected framework revision and Rust toolchain. Record dependency resolution. Native Rust SDK 1.0 is an evaluated starting point, not permission to silently upgrade unrelated framework pins.

2. Ship a headless worker executable and a Rust start/query/cancel client. Require Temporal address, namespace, task queue, SQLite store path, provider model, and runtime credentials through explicit configuration. Fail before polling on invalid catalogs or inaccessible stores.

3. Register versioned workflow/activity names with one immutable runtime catalog. Queue routing is explicit and shared between start client and worker. App contribution generation arrives in Phase 6; the initial Rust host composes the same registration types directly.

4. Workflows own orchestration and use only deterministic state transitions. Code steps, inference turns, tool calls, and ledger writes are activities. Random IDs and wall time are generated at supported deterministic/side-effect boundaries, never from arbitrary workflow library calls.

5. For agents, workflow state carries the transcript, counters, stable invocation ID, turn number, and allowed schema/tool versions. Each completed provider activity result is recorded by Temporal; the pure loop transition chooses the next scheduled effect. A full conversation is never hidden in one retryable activity.

6. Schedule tool calls as separate named activities with stable invocation keys. Read-only/idempotent activities can use explicit bounded retries; non-idempotent tools have automatic retries disabled until Phase 5's recovery policy can resolve uncertain completion.

7. Create/reuse logical run and step identities through idempotent ledger activities. Attempt identity includes the relevant Temporal execution/activity attempt information. Activity results are typed objects; transient provider response wrappers do not leak into public workflow outputs.

8. Use explicit activity deadlines and heartbeat long-running cooperative work. Map cancellation and retryable errors through the runtime contract. Validation/configuration errors are non-retryable. Completion/failure ledger writes are idempotent and may retry independently.

9. The initial host uses one local SQLite file with supported concurrent Rust connections. No database network share or remote worker writing that file is assumed. Client process exit does not terminate the separately supervised worker.

10. Provide a basic real-server start-to-finish path now. Phase 5 owns crash-window dispatch reconciliation, durable decision reconsideration, and unsafe-effect handling; this phase must document those limits rather than claim complete recovery.

## Testing decisions

- Drive a real Temporal dev server with the public Rust client and worker, a code step, a typed provider step, and a read-only Rust tool. Compare the workflow result with SQLite records.

- Use a deterministic HTTP fixture for retry, malformed result, and timeout cases; include one live inference run with the actual model recorded.

- Restart a worker after a completed activity and verify that Temporal reuses that recorded result. Capture and replay a representative Rust workflow history.

- Test bad queue/configuration/registration startup, graceful shutdown, cancellation delivery, and typed result decoding. Prior art: current Temporal activity/plugin tests plus real server integration.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

Python history takeover, public GraphQL control, UI, remote SQLite access, unbounded provider retries, and complete side-effect recovery before Phase 5.

## Further notes

Depends on: CODING-2067, CODING-2068. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

