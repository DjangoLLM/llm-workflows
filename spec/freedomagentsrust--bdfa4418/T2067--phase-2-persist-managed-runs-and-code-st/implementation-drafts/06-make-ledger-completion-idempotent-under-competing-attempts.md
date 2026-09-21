# 06. Make ledger completion idempotent under competing attempts

## Parent

CODING-2067. See [implementation specification](../SPEC.md).

## What to build

Repeated completion and concurrent writers preserve the accepted result rather than letting a late attempt overwrite it.

## Acceptance criteria

- [ ] Identical completion is idempotent; stale or conflicting revision/attempt writes fail visibly.
- [ ] File-store foreign keys/WAL and bounded busy handling are configured and exercised with competing connections.
- [ ] No external work holds a SQLite write transaction.
- [ ] Migration up/down, generated drift, and public ledger integration checks pass.

## Blocked by

- Draft 05: Record step failures and preserve valid lineage under CODING-2067.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

