# 26. Back up, restore, and upgrade the SQLite runtime safely

## Parent

CODING-2073. See [implementation specification](../SPEC.md).

## What to build

Operators can restore a consistent ledger and upgrade it without losing identities or silently accepting an incompatible schema.

## Acceptance criteria

- [ ] Use a SQLite-consistent backup or quiesced checkpoint, including active WAL semantics.
- [ ] Restore verifies integrity and installation/schema compatibility before new work.
- [ ] Serialize migrations and reject too-new schemas from older binaries.
- [ ] Test backup during writes, restore/reopen/new execution, supported upgrade, and bounded worker shutdown.

## Blocked by

- Draft 25: Install and run packaged Rust artifacts in a clean Project under CODING-2073.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

