# 23. Resume interrupted imports without publishing partial history

## Parent

CODING-2072. See [implementation specification](../SPEC.md).

## What to build

A failed import can resume safely, while changed snapshots and identity conflicts fail without exposing a partial successful import.

## Acceptance criteria

- [ ] Checkpoint by snapshot ID and checksums and make retries idempotent.
- [ ] Terminate/restart the importer at multiple points and verify final integrity.
- [ ] Reject changed checkpointed input and conflicting live UUIDs.
- [ ] Record actual legacy source-schema evidence when available; fixture success must not be presented as live production migration.

## Blocked by

- Draft 22: Validate and import a historical execution snapshot under CODING-2072.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

