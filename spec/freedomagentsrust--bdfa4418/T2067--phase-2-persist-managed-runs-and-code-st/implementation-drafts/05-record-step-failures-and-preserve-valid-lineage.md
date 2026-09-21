# 05. Record step failures and preserve valid lineage

## Parent

CODING-2067. See [implementation specification](../SPEC.md).

## What to build

Preprocessing, execution, and postprocessing failures remain auditable, while related steps retain correct directed lineage.

## Acceptance criteria

- [ ] Each failure records its stage, safe error, terminal attempt state, and timestamps.
- [ ] Success is committed only after output validation/postprocessing.
- [ ] Reject missing, cross-run, self, and cyclic parent references.
- [ ] Run/step deletion maintenance semantics and agent-reference nulling have real SQLite tests.

## Blocked by

- Draft 04: Execute and reopen a code pipeline in SQLite under CODING-2067.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

