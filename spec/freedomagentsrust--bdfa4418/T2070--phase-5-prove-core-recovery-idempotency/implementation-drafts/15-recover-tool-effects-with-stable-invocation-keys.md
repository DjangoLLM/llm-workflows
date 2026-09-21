# 15. Recover tool effects with stable invocation keys

## Parent

CODING-2070. See [implementation specification](../SPEC.md).

## What to build

A completed external mutation is deduplicated on retry, while an ambiguous non-idempotent action waits for explicit resolution.

## Acceptance criteria

- [ ] Persist effect intent and reuse the invocation key across attempts.
- [ ] A durable external fixture demonstrates deduplication/outcome lookup across a crash after remote commit.
- [ ] Tools without deduplication or outcome recovery enter WAITING_FOR_INPUT on uncertainty.
- [ ] Resolve/cancel controls are idempotent, reject stale revisions, and retain actor/reason; no exactly-once claim for arbitrary services.

## Blocked by

- Draft 14: Retry branches without changing recorded decisions under CODING-2070.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

