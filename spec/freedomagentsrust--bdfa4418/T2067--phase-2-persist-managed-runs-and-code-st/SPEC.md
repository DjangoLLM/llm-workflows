# Phase 2: Persist managed runs and code steps in SQLite

CODING-2067 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

Code steps need a durable execution ledger. The current ORM eagerly creates records and does not distinguish every logical step from its retry attempts, so a direct mechanical model translation would carry ambiguous recovery semantics into Rust.

## Solution

Persist managed runs, logical steps, attempts, agent invocations, and lineage in SQLite through generated SeaORM Models. A Rust consumer can execute code steps, restart, and inspect both successful and failed outcomes.

## User stories

1. As an operator, I want to reopen a store after restart, so that completed work remains inspectable.
2. As a pipeline author, I want to record input and output for each step, so that I can explain the run.
3. As a developer, I want to record preprocessing failures, so that a failed step does not remain pending.
4. As a developer, I want to record postprocessing failures, so that invalid final output is not marked successful.
5. As a workflow author, I want to separate attempts from logical steps, so that retries do not duplicate the pipeline graph.
6. As a consumer, I want to retain UUID identities, so that references survive import and restart.
7. As a pipeline author, I want to persist directed parent links, so that branch lineage remains visible.
8. As an operator, I want to receive bounded database contention errors, so that workers do not hang indefinitely.
9. As a maintainer, I want to apply and reverse migrations, so that schema changes are reviewable.
10. As an API author, I want to protect runtime-owned outcomes, so that callers cannot fabricate success.

## Implementation decisions

1. Keep all execution ledger tables in one framework Module. Add PipelineRun, PipelineStep, StepAttempt, AgentRun, and a directed step-parent join Model. Additional audit Models are introduced by the phases that need them, through forward reversible migrations.

2. Store UUIDs in a canonical, indexed representation verified through generation. Preserve JSON null separately from an absent/unset outcome, validate JSON values on read/write, and use UTC timestamps with one documented representation. Do not expose SQLite rowids as public identities.

3. PipelineRun carries pipeline/definition version, root payload, context, request identity, workflow identity, lifecycle revision, timestamps, and terminal outcome. PipelineStep carries run, registered key, occurrence key, order metadata, state, input/output, and parent relations. Order metadata is observational rather than an implicit execution scheduler.

4. Enforce uniqueness for a run's request key, a logical step's occurrence key within its run, and an attempt number within a logical step. AgentRun identifies the managed invocation; link an attempt to that invocation without treating every provider turn as another logical step.

5. Use PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED, and WAITING_FOR_INPUT for run/step lifecycle where applicable. Attempts use PENDING, RUNNING, SUCCEEDED, FAILED, or CANCELLED. A failed retryable attempt does not by itself fail the logical step. Phase 5 implements waiting/resume policy; reserve its contract now.

6. Record preprocessing, execution, and postprocessing within the tracked attempt lifecycle. Only successfully validated postprocessed output can commit success. Store safe classified errors and terminal timestamps on failure. Failed setup before an accepted run creates no misleading success record.

7. Terminal commits use an expected revision/attempt identity. Repeated identical completion is idempotent; conflicting or stale completion is rejected. Never let a late attempt overwrite a newer outcome. Only runtime lifecycle services may mutate status/output.

8. Validate that parent IDs exist in the same run and reject self-links and cycles. Preserve run-to-step cascade and nullable agent references deliberately; normal runtime APIs do not expose deletion of execution history. Tests document explicit maintenance deletion behavior.

9. Use short transactions for related ledger writes. No network call, tool action, or wait holds a SQLite write transaction. Enable foreign keys and use WAL for file stores, with a bounded busy timeout and a documented capped retry policy for safe transactions.

10. Generated entities remain authoritative. Expose the minimum supported Store vocabulary needed by background services through the framework boundary; document any necessary repository/write exception rather than bypassing generation. Configure only SQLite now.

11. Persist request/workflow identity now, but do not claim atomic remote workflow start in this phase. Phase 5 adds durable dispatch intent and reconciliation. File stores belong to one local host deployment; shared network filesystems and multi-host writers are unsupported.

## Testing decisions

- Run a two-code-step pipeline through the public service against a temporary file database, close it, reopen it, and inspect output, attempts, and lineage.

- Exercise preprocessing/execution/postprocessing failures, duplicate start/attempt identifiers, idempotent completion, stale completion, wrong-run parents, and cycle rejection.

- Run real SQLite migration up/down, fresh generation, UUID/JSON/null/time round trips, foreign-key deletion rules, and bounded two-connection contention tests.

- Prior art: existing model and pipeline integration tests, standalone migration-graph checks, and the target framework's real migrated-store tests. Assert persisted behavior, not generated source text.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

Provider inference, remote dispatch guarantees, automatic recovery policy, SQL backend portability work, arbitrary CRUD over runtime state, and UI.

## Further notes

Depends on: CODING-2066. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

