# 24. Rehearse versioned workflow cutover and rollback

## Parent

CODING-2072. See [implementation specification](../SPEC.md).

## What to build

New requests move to Rust workflows while legacy histories remain separate, and a rollback rehearsal preserves later Rust work.

## Acceptance criteria

- [ ] Route new work by versioned type/queue without sending Python histories to Rust workers.
- [ ] Imported history stays inert and legacy drain remains external to the new runtime.
- [ ] Rehearse freeze/snapshot/import/switch and rollback after new writes/external effects.
- [ ] Provide an operator procedure and evidence; do not execute destructive production cutover.

## Blocked by

- Draft 23: Resume interrupted imports without publishing partial history under CODING-2072.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

