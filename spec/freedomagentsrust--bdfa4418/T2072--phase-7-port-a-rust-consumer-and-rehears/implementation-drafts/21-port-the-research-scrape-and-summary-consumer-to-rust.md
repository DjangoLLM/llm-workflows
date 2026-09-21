# 21. Port the research scrape-and-summary consumer to Rust

## Parent

CODING-2072. See [implementation specification](../SPEC.md).

## What to build

A reusable Rust consumer validates a URL, retrieves content through the configured native HTTP tool, and produces a typed agent summary.

## Acceptance criteria

- [ ] Port the bounded existing scrape input/output and provider error contract without a Python service.
- [ ] Register through installed App contributions and execute through the public workflow/command path.
- [ ] Exercise valid/invalid URLs, retrieval failure, typed tool output, and summary persistence.
- [ ] Use controlled provider fixtures and record any separately required live-provider evidence.

## Blocked by

- Draft 19: Recover separate-worker updates through cursor subscriptions under CODING-2071.
- Draft 20: Expose permitted Rust tools over MCP STDIO under CODING-2071.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

