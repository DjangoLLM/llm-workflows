# 16. Pass the integrated headless core recovery gate

## Parent

CODING-2070. See [implementation specification](../SPEC.md).

## What to build

A fresh Rust consumer demonstrates durable code-plus-agent execution and recovery without GraphQL or a UI.

## Acceptance criteria

- [ ] Reconcile terminal ledger writes after crashes without rerunning their external effects.
- [ ] Run duplicate start, worker restart, stale completion, decision retry/reconsider, uncertain tool, cancellation, and replay scenarios.
- [ ] Record real inference evidence and versions; unavailable live dependencies cannot count as passed acceptance.
- [ ] Publish the headless run command and pure Rust dependency proof.

## Blocked by

- Draft 15: Recover tool effects with stable invocation keys under CODING-2070.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

