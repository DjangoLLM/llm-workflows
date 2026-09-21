# 07. Persist one native typed inference result in Rust

## Parent

CODING-2068. See [implementation specification](../SPEC.md).

## What to build

A managed Rust agent calls the configured provider and returns a nested typed result persisted in SQLite.

## Acceptance criteria

- [ ] Use direct Rust OpenAI Responses HTTP with an explicitly configured model and runtime-only credentials.
- [ ] Validate supported schema before HTTP and validate/deserialise the final value before success.
- [ ] Reject refusal, incomplete output, extra fields, malformed JSON, and unsupported schema constructs.
- [ ] Deterministic HTTP-boundary tests and a recorded real nested-output acceptance case exercise the public managed-agent path.

## Blocked by

- Draft 06: Make ledger completion idempotent under competing attempts under CODING-2067.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

