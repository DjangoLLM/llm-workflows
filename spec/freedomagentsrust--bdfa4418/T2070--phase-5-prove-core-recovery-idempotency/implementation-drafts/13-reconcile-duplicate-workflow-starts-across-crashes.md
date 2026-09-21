# 13. Reconcile duplicate workflow starts across crashes

## Parent

CODING-2070. See [implementation specification](../SPEC.md).

## What to build

Repeated or concurrent submissions create one logical run even if the process dies between SQLite commit and Temporal acknowledgement.

## Acceptance criteria

- [ ] Atomically persist request fingerprint, stable workflow ID, and dispatch intent.
- [ ] Recover both pre-acceptance and post-acceptance crash windows using the same identity.
- [ ] Return the existing run for identical input and conflict for reused keys with different input.
- [ ] Real SQLite/Temporal process-termination tests prove no lost intent or duplicate logical start.

## Blocked by

- Draft 12: Expose worker health, cancellation, and graceful shutdown under CODING-2069.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

