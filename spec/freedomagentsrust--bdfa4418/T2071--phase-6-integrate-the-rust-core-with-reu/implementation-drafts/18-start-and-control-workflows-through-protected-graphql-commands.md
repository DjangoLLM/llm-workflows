# 18. Start and control workflows through protected GraphQL commands

## Parent

CODING-2071. See [implementation specification](../SPEC.md).

## What to build

A generated client contract can start/read/control a run while raw generated writes cannot fabricate outcomes.

## Acceptance criteria

- [ ] Preserve generated read/filter/pagination contracts where safe and suppress runtime-owned writes with documented framework exceptions.
- [ ] Command requests carry idempotency keys and expected revisions and use the proven core service.
- [ ] Return safe errors and never expose credentials.
- [ ] Drive the behavior through headless HTTP and Tauri Rust transport tests without a product UI.

## Blocked by

- Draft 17: Compose execution contributions from two reusable Apps under CODING-2071.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

