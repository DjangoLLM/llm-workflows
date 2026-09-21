# 08. Complete a typed Rust tool round trip inside the agent loop

## Parent

CODING-2068. See [implementation specification](../SPEC.md).

## What to build

An agent selects a permitted Rust tool, receives its validated result, and produces a checked final answer.

## Acceptance criteria

- [ ] Use the shared pure transition function and immutable tool registry.
- [ ] Preserve instructions, tool call identifiers, order, and required provider continuation data.
- [ ] Reject unknown/forbidden tools and invalid arguments before invocation; validate tool output.
- [ ] Run real Rust tools and SQLite against a provider fixture, plus one live read-only tool round trip.

## Blocked by

- Draft 07: Persist one native typed inference result in Rust under CODING-2068.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

