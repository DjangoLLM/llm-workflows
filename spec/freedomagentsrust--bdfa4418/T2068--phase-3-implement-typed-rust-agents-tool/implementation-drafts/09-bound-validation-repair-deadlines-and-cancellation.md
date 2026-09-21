# 09. Bound validation repair, deadlines, and cancellation

## Parent

CODING-2068. See [implementation specification](../SPEC.md).

## What to build

Malformed model output can be corrected within a fixed budget, while timeout/cancellation reliably ends owned local work and records failure.

## Acceptance criteria

- [ ] Apply the specified total/per-operation deadlines, turn budget, and repair budget without resetting them on repair.
- [ ] Exercise malformed-then-valid, exhausted repair, provider failure, hanging tool/provider, and cancellation.
- [ ] Do not hide transport retries or automatically repeat unsafe effects.
- [ ] Safe terminal errors and resource cleanup are verified at the managed-agent boundary; direct-loop durability limits are documented.

## Blocked by

- Draft 08: Complete a typed Rust tool round trip inside the agent loop under CODING-2068.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

