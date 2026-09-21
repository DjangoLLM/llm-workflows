# Phase 8: Package and verify the Rust migration for delivery

CODING-2073 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

Individually passing phases do not establish that a new operator can install, run, upgrade, and recover the integrated Rust runtime. Delivery also needs proof that no interpreter worker has slipped back into the deployment.

## Solution

Package the headless runtime and reusable App with reproducible builds, operational commands, and one end-to-end release acceptance record. Ship the Rust core and its integrations without a new UI.

## User stories

1. As an operator, I want to install pinned artifacts, so that the deployed version is reproducible.
2. As an operator, I want to start the worker with explicit configuration, so that local operation is predictable.
3. As an operator, I want to check readiness, so that a running process is not mistaken for a working worker.
4. As an operator, I want to shut down gracefully, so that owned tasks have a bounded cleanup period.
5. As an operator, I want to back up SQLite consistently, so that WAL writes are not lost.
6. As an operator, I want to restore and validate a backup, so that recovery produces a usable ledger.
7. As an operator, I want to upgrade the schema safely, so that existing IDs and records survive.
8. As a consumer author, I want to install the reusable App into a clean Project, so that delivery proves reuse.
9. As a maintainer, I want to run an integrated acceptance command, so that release evidence covers cross-phase behavior.
10. As a reviewer, I want to inspect runtime dependencies and limitations, so that pure Rust and local deployment claims are verifiable.

## Implementation decisions

1. Deliver versioned Rust libraries, a headless worker/service executable, a control/maintenance CLI, a Rust MCP executable if separate, and reusable App sources/metadata. Lock Rust and framework dependencies and document supported toolchain/platform versions.

2. Keep build tooling separate from runtime requirements. Framework JavaScript generation may be required for development, but installed execution binaries never launch Python, Node, Pydantic AI, pi-worker, or a coding CLI. External Temporal and the configured provider remain explicit services.

3. Provide commands/procedures for configuration validation, database migration, worker start, readiness, run submission/status/control, import validation, backup, and restore. Secrets come from environment or an operator-managed secret file and are never printed or embedded in generated artifacts.

4. Readiness verifies catalog validity, schema version, local Store access, and Temporal connectivity/polling initialization. Provider credentials are checked for presence without making billable inference on every health probe. Live provider health is an explicit diagnostic.

5. Support a separately supervised worker with signal-driven graceful shutdown and a bounded cleanup timeout. Exiting the desktop shell does not imply that separately supervised work stops. If the worker is absent, Temporal retains work until a compatible worker returns.

6. Use a SQLite-consistent backup operation or quiesced/checkpointed copy; never copy only the main file while ignoring an active WAL. Restore verifies integrity, migration compatibility, and installation identity before accepting new work.

7. Run forward schema migrations once under an explicit startup/maintenance lock. An older binary rejects a newer unsupported schema. Reversible development migrations are not a guarantee of lossless production downgrade; rollback requires a compatible snapshot and accounting for later work.

8. Verify clean App installation, source relocation, generated contracts, and headless web/Tauri Rust host integration. Desktop and web stores remain independent installations. No synchronization or public multi-user deployment is implied.

9. Produce an acceptance record naming revisions, binaries, model, Temporal version, commands, platform, and sanitized outcomes. Include the code-plus-agent workflow, keyed tool effect, crash recovery, replay, GraphQL/MCP, consumer/import rehearsal, and backup/restore.

10. Treat unavailable live provider/Temporal checks as incomplete release acceptance. Deterministic CI can run without credentials, but release sign-off requires the explicitly recorded live cases.

11. Document future database replacement as follow-up work with stable UUID/payload contracts. Do not ship speculative Postgres support or a custom multi-database abstraction to satisfy this ticket.

## Testing decisions

- From a clean consumer environment, build/install pinned artifacts, create a fresh SQLite ledger, start the Rust worker, submit the reference workflow, inspect output, and stop/restart cleanly.

- Run backup during representative writes, restore into a separate location, verify integrity, and execute new work without losing existing identity. Exercise supported upgrade and too-new-schema rejection.

- Run the integrated public-behavior matrix and relevant framework verify/drift/seal checks, Rust tests, transport checks, replay, and live inference. Record unavailable checks distinctly.

- Inspect binaries/dependency trees and run with Python/Node absent from runtime PATH. Test a separate worker and API host lifecycle.

- Prior art: target clean-project acceptance/build tests and phase-level execution/recovery/transport tests. Add integration scenarios only where composition introduces a new failure mode.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

Product UI, public multi-user hosting, automatic updates/signing infrastructure, store synchronization, another SQL backend, all historical consumers, and broad model/provider parity.

## Further notes

Depends on: CODING-2071, CODING-2072. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

