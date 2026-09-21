# 19. Recover separate-worker updates through cursor subscriptions

## Parent

CODING-2071. See [implementation specification](../SPEC.md).

## What to build

A subscriber sees committed lifecycle changes from a separate worker and catches up after disconnect without losing state.

## Acceptance criteria

- [ ] Write a monotonic durable change record in the lifecycle transaction.
- [ ] Use local notification/IPC as a wake-up; the change log remains authoritative.
- [ ] Close snapshot/subscription races, deduplicate by cursor/revision, and return explicit snapshot-required on expired cursors.
- [ ] Separate-process tests cover missed notifications, disconnect, reconnect during snapshot, and bounded cleanup without client polling.

## Blocked by

- Draft 18: Start and control workflows through protected GraphQL commands under CODING-2071.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

