# Phase 5: Prove core recovery, idempotency, and durable decisions

CODING-2070 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

A happy-path Temporal demo does not prove the core survives duplicate submission, ambiguous external completion, or failure between remote execution and local bookkeeping. Those gaps can repeat effects or silently change a decision.

## Solution

Complete the core by making starts and lifecycle writes idempotent, recording explicit branch decisions, and testing crash recovery at the real process boundaries. This is the core-working release gate.

## User stories

1. As a caller, I want to retry a start request safely, so that one logical run is created.
2. As an operator, I want to restart after a dispatch crash, so that accepted work is not lost.
3. As a workflow author, I want to reuse a recorded branch decision, so that retry does not change intent.
4. As a workflow author, I want to request reconsideration explicitly, so that a new choice has a separate audit record.
5. As a tool author, I want to receive a stable invocation key, so that external writes can deduplicate.
6. As an operator, I want to pause uncertain effects, so that the runtime does not blindly repeat them.
7. As a caller, I want to cancel durably, so that run state converges after restart.
8. As an operator, I want to resume a waiting run explicitly, so that human decisions are recorded.
9. As a maintainer, I want to replay saved histories, so that workflow changes preserve determinism.
10. As a consumer, I want to run the full core without an API shell, so that core readiness does not depend on UI work.

## Implementation decisions

1. Add a durable dispatch-intent Model. Accepting a start atomically records the run, caller request key, canonical request fingerprint, stable workflow ID, and unsent intent in SQLite. Identical duplicate submissions return the same run; reusing a key with different content returns a conflict.

2. A Rust dispatcher reconciles intent against Temporal using deterministic workflow identity and an explicit duplicate/reuse policy. It retries ambiguous starts without allocating another run. Store Temporal execution identity after acknowledgement; a crash before that commit is resolved by lookup/retry of the same identity. Never claim a distributed SQLite/Temporal transaction.

3. Keep a durable ledger of semantic operations keyed by run, logical occurrence, decision revision, turn, and tool-call position as applicable. Attempt records remain distinct. Conditional completion prevents old activity results from overwriting a newer accepted terminal state.

4. Persist a decision record containing input reference, agent definition/schema version, validated choice, allowed branch set, and decision revision. RetryBranch retains this decision ID and repeats only the branch's declared retry boundary. Reconsider creates a new explicit decision invocation linked to the previous decision.

5. Separate the workflow's authoritative execution history from the query ledger. Idempotent ledger activities reconcile accepted results. A failed reconciliation is visible as pending/failed recording, never silent success. Provide an operator reconciliation command that does not rerun the original effect.

6. Classify tools as read-only, idempotent with a provider-supported key, or non-idempotent/uncertain. Persist tool invocation intent and use the same key across retries. A local completion checkpoint alone cannot resolve a crash after a remote side effect but before local commit.

7. For the representative mutation, implement an external fixture that durably deduplicates invocation keys and supports outcome lookup. If a real tool cannot offer deduplication or outcome recovery, ambiguous completion moves the workflow to WAITING_FOR_INPUT rather than retrying automatically.

8. Expose idempotent Rust control commands for cancel, retry branch, reconsider, and resolve uncertain effect. Each command has a request ID and expected decision/state revision. Reject contradictory or stale controls. Record actor/reason, even for the initial single-user host. No arbitrary status setter is public.

9. Cancellation closes cooperative activities and marks the workflow/ledger CANCELLED only after the defined cleanup/recording boundary. Unexpected worker death is not cancellation. Waiting runs require an explicit permitted resolution; exhausted retries follow the declared fail-or-wait policy.

10. Keep bounded recovery and retry settings explicit. Preserve recorded decisions during process crashes; do not silently fall back to another model or provider. Core v1 uses external Temporal plus local SQLite and one native provider.

11. Declare core readiness only when the public headless example, duplicate/crash matrix, history replay, and live inference acceptance all pass. Real credentials/server unavailability is an acceptance blocker, not a skipped success.

## Testing decisions

- At the public start/control interface, inject process termination before/after SQLite intent commit, Temporal acceptance, acknowledgement commit, tool external commit, and terminal ledger recording. Assert stable identity and correct recovery after restart.

- Concurrently submit identical and conflicting request keys. Verify one workflow/run for identical input and an explicit conflict for changed input.

- Use provider call counters and durable fake external effects to prove branch retry does not infer again, reconsider does, keyed effects occur once, and uncertain effects wait for a recorded resolution.

- Replay captured histories; test stale controls, cancellation/restart, retry exhaustion, and ledger reconciliation without repeating effects. Run one live typed-inference workflow with the real provider.

- Prior art: current workflow helper/failure tests and framework transaction-conflict tests. Tests drive complete public behaviors with real SQLite and Temporal, not only helper functions.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

Exactly-once claims for arbitrary remote services, multi-user policy, GraphQL/UI controls, automatic migration of old Python workflow histories, and database replacement.

## Further notes

Depends on: CODING-2069. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

