# 02. Validate execution definitions and dispatch through one Rust catalog

## Parent

CODING-2066. See [implementation specification](../SPEC.md).

## What to build

An application composes step, tool, and agent definitions once and either starts with a valid catalog or fails with an actionable configuration error.

## Acceptance criteria

- [ ] Reject duplicate stable names, missing references, invalid deadlines, and unsupported declared contract shapes before dispatch.
- [ ] The public code-step path resolves registered behavior by name and preserves logical occurrence identity.
- [ ] Introduce the pure agent transition/provider-turn/tool-call contracts without network effects.
- [ ] Demonstrate classified safe errors and redacted configuration through the consumer example.

## Blocked by

- Draft 01: Run a typed Rust code step from a standalone consumer under CODING-2066.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

