# 04. Execute and reopen a code pipeline in SQLite

## Parent

CODING-2067. See [implementation specification](../SPEC.md).

## What to build

A Rust caller runs two code steps, closes the process, and reads their durable output and lifecycle from a reopened SQLite store.

## Acceptance criteria

- [ ] Use reversible migrations and generated Models for runs, logical steps, attempts, agent runs, and parent links.
- [ ] Preserve UUID, JSON/null, UTC timestamps, indexes, and foreign-key behavior.
- [ ] Create attempts under stable logical occurrence keys and enforce uniqueness.
- [ ] The public headless example proves persistence after reopen and fresh-store generation passes.

## Blocked by

- Draft 03: Prove supported host capabilities for headless execution under CODING-2066.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

