# 01. Run a typed Rust code step from a standalone consumer

## Parent

CODING-2066. See [implementation specification](../SPEC.md).

## What to build

A separate headless Rust program executes a registered deterministic code step and receives a typed result through the new public core.

## Acceptance criteria

- [ ] Record the actual implementation workspace and integrated baseline before editing; preserve existing work.
- [ ] Build and execute the example without Tauri, Python, Node, or network services.
- [ ] Public request/result/error contracts round-trip with stable UUID identities and reject an unsupported envelope version.
- [ ] Cargo tests exercise consumer-visible behavior rather than private helpers.

## Blocked by

None. Can start immediately after the breakdown is approved.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

