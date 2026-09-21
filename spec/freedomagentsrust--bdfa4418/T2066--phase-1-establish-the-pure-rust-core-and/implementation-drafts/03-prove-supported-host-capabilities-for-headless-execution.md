# 03. Prove supported host capabilities for headless execution

## Parent

CODING-2066. See [implementation specification](../SPEC.md).

## What to build

The same core consumer can use host-supplied execution capabilities without depending on GraphQL request context or violating framework Module rules.

## Acceptance criteria

- [ ] Add the smallest supported framework vocabulary and prove it with a fixture Module and headless host.
- [ ] Keep generated Model types authoritative and generic execution contracts separate.
- [ ] Module import/dependency checks still pass; no arbitrary allowlist widening.
- [ ] Publish the first provider/schema decisions and public consumer compile proof.

## Blocked by

- Draft 02: Validate execution definitions and dispatch through one Rust catalog under CODING-2066.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

