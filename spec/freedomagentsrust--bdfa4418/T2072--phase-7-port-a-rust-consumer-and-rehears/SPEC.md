# Phase 7: Port a Rust consumer and rehearse data and workflow cutover

CODING-2072 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

A reusable runtime needs evidence from a real consumer, and a new SQLite ledger must not lose existing execution history. Copying tables does not transfer Temporal workflow history or safely redirect in-flight work.

## Solution

Port a bounded research-tool consumer to Rust and rehearse a versioned historical import plus new-work cutover. Keep legacy deployments separate while proving the new runtime has no Python dependency.

## User stories

1. As a consumer author, I want to run an existing research tool from Rust, so that the new contracts solve a real integration.
2. As an operator, I want to validate an import before writing, so that bad snapshots cannot corrupt the ledger.
3. As an operator, I want to preserve historical UUIDs and lineage, so that old references still resolve.
4. As an operator, I want to resume an interrupted import, so that migration does not require starting over.
5. As a reviewer, I want to compare source and target records, so that data loss is visible.
6. As an operator, I want to separate historical runs from live scheduling, so that import cannot restart completed work.
7. As an operator, I want to route new work to versioned Rust workflows, so that legacy histories do not reach incompatible code.
8. As an operator, I want to let legacy work drain separately, so that the new runtime remains Python-free.
9. As an operator, I want to rehearse rollback after new writes, so that rollback does not silently discard progress.
10. As a maintainer, I want to use Rust migration tools, so that cutover does not add a Python bridge.

## Implementation decisions

1. Use the existing research consumer's scrape-URL behavior as the bounded real integration. Port its typed input/output and one configured HTTP provider adapter to Rust, with a code validation step and a typed agent summary step. Do not port the complete Plane or research application.

2. Preserve the selected consumer's documented request validation and safe provider errors. The native workflow must run through installed App contributions, the core ledger, and the Phase 6 command contract. The consumer provider is independently configured; no Python service performs the call.

3. Define a versioned JSON Lines snapshot containing a manifest and typed records for runs, logical steps, agent runs, and parent links. Include source identity/revision, snapshot ID, record counts, and content checksums. Accept a documented raw export or provide a Rust reader/exporter for the actual legacy database only after its schema is identified.

4. Never require Django or Python to execute the migration tool. If the production source schema/export is unavailable, deliver fixture-based tooling and mark live-source rehearsal incomplete. Do not infer production mappings solely from old migration filenames.

5. Validate all records and references in a staging area before promoting a snapshot. Reject duplicate/conflicting UUIDs, malformed JSON, unknown required statuses, missing parents, cycles, invalid timestamps, and incompatible schema versions with a record-level report.

6. Preserve source UUIDs and source fields faithfully, with an explicit source-to-target mapping. Historical records missing attempt information remain marked imported/unknown rather than inventing retry history. Imported runs are read-only historical entries and never create dispatch intent.

7. Resume import by snapshot/checksum and checkpoint; retrying byte-identical input is idempotent. A changed record under an already-imported snapshot or conflicting existing live UUID fails. Commit visibility only after full integrity validation, or atomically mark the import incomplete so it is excluded from normal completed-history reads.

8. Verify counts by record type/status, canonical payload hashes, timestamps, and relationship membership. Record any intentionally unmapped legacy fields in a report. Do not silently coerce scalar payloads into objects when history permits arbitrary JSON.

9. Cutover routes only new work to versioned Rust workflow types/queues. Existing Python workflows stay on their old deployment until drained; neither their workers nor their runtime become a dependency of FreedomAgentsRust. Any proposed history takeover requires separate replay proof and authorization.

10. Rehearse a freeze/snapshot/import/switch sequence and a rollback sequence with new Rust writes. Rollback stops new submissions, preserves the Rust store/history, and resolves in-flight effects before routing elsewhere. Reverting binaries alone does not undo external work.

11. Production destructive actions and live cutover are not authorized by this specification. Provide runnable rehearsals and an operator procedure. Retain SQLite for target persistence.

## Testing decisions

- Run the ported scrape consumer against a controlled HTTP service through the public Rust workflow/API. Exercise successful retrieval/typed summary, invalid URL, provider failure, and tool schema compatibility.

- Import fixtures with nested/scalar/null history payloads, successful/failed runs, parent links, and missing legacy attempt metadata; compare counts and canonical records after reopening SQLite.

- Crash/retry import, alter a checkpointed snapshot, introduce UUID conflicts and broken references, and prove failure does not publish partial completed history.

- Rehearse new-work routing and rollback with a fake external effect ledger, keeping imported history inert. Live source/provider validation is recorded separately when accessible.

- Prior art: existing research tool provider tests, source migration-graph tests, and target upgrade/relocation tests.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

All consumer applications, Python adapters, new database backend, destructive production migration, unproven history takeover, and comprehensive provider parity.

## Further notes

Depends on: CODING-2071. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

