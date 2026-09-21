# 14. Retry branches without changing recorded decisions

## Parent

CODING-2070. See [implementation specification](../SPEC.md).

## What to build

A branch retry keeps its accepted agent choice; explicit reconsideration records a new decision and audit link.

## Acceptance criteria

- [ ] Persist validated choice, allowed branch set, definition/schema version, and decision revision.
- [ ] Idempotent control requests enforce expected state/decision revisions.
- [ ] Provider counters prove RetryBranch performs no new decision inference and Reconsider does.
- [ ] Exhausted retry and waiting/resume policy produce observable lifecycle records.

## Blocked by

- Draft 13: Reconcile duplicate workflow starts across crashes under CODING-2070.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

