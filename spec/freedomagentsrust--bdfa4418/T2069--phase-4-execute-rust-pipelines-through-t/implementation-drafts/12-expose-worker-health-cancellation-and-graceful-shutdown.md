# 12. Expose worker health, cancellation, and graceful shutdown

## Parent

CODING-2069. See [implementation specification](../SPEC.md).

## What to build

Operators can diagnose startup and stop or cancel work without silently losing lifecycle state.

## Acceptance criteria

- [ ] Headless readiness identifies invalid catalogs, inaccessible stores, and Temporal connection failures.
- [ ] Public Rust query/cancel calls map to typed lifecycle outcomes.
- [ ] Long-running cooperative work receives cancellation/heartbeat handling and bounded shutdown.
- [ ] Retryable activity errors and non-retryable contract errors behave distinctly in real-server tests.

## Blocked by

- Draft 11: Resume a Temporal agent across recorded turns and tool activities under CODING-2069.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

