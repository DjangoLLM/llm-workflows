# 27. Verify and record the integrated Rust release

## Parent

CODING-2073. See [implementation specification](../SPEC.md).

## What to build

One release acceptance record proves the complete installed runtime across execution, recovery, transports, consumer migration, and operations.

## Acceptance criteria

- [ ] Run the cross-phase public-behavior matrix and relevant framework generation/drift/seal checks.
- [ ] Include Temporal replay/recovery, GraphQL/MCP, real inference, migrated consumer/import rehearsal, and backup/restore.
- [ ] Record versions, commands, sanitized outcomes, and unavailable checks explicitly.
- [ ] Document local/single-user scope, independent stores, external Temporal/provider dependencies, and deferred UI/database replacement.

## Blocked by

- Draft 26: Back up, restore, and upgrade the SQLite runtime safely under CODING-2073.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

