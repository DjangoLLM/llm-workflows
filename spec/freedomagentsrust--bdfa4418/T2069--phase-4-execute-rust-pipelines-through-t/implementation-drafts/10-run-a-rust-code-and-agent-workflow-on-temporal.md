# 10. Run a Rust code-and-agent workflow on Temporal

## Parent

CODING-2069. See [implementation specification](../SPEC.md).

## What to build

A Rust client submits a workflow to a Rust worker and receives the result of a code step followed by typed inference.

## Acceptance criteria

- [ ] Pin and prove compatible Temporal Rust dependencies without unrelated framework upgrades.
- [ ] Validate queue/store/catalog configuration before polling.
- [ ] Schedule database and inference effects as activities with typed object payloads.
- [ ] A real Temporal dev-server test compares the returned result with SQLite and includes recorded live inference.

## Blocked by

- Draft 09: Bound validation repair, deadlines, and cancellation under CODING-2068.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

