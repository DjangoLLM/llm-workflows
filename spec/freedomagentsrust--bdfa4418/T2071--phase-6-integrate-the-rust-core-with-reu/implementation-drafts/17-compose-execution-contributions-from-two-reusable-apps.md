# 17. Compose execution contributions from two reusable Apps

## Parent

CODING-2071. See [implementation specification](../SPEC.md).

## What to build

A clean consumer Project installs two Apps and obtains matching worker/API runtime catalogs through supported generated registration.

## Acceptance criteria

- [ ] Extend the supported host registration mechanism and inject Rust execution capabilities.
- [ ] Reject duplicate/missing/mismatched contributions at generation/startup.
- [ ] Exercise source relocation and preserve stable registration identities.
- [ ] Generation/drift/seal checks pass without hand-edited registries or Module dependency bypasses.

## Blocked by

- Draft 16: Pass the integrated headless core recovery gate under CODING-2070.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

