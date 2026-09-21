# 25. Install and run packaged Rust artifacts in a clean Project

## Parent

CODING-2073. See [implementation specification](../SPEC.md).

## What to build

A clean consumer installs the reusable App and pinned Rust artifacts, starts the worker, and executes the reference workflow.

## Acceptance criteria

- [ ] Package headless runtime/control/MCP artifacts with explicit config and secret sourcing.
- [ ] Exercise clean App generation/installation and existing web/Tauri Rust host integration.
- [ ] Readiness and supervised shutdown match the worker contract.
- [ ] Execution works with Python/Node absent from runtime PATH; development generation tooling is documented separately.

## Blocked by

- Draft 24: Rehearse versioned workflow cutover and rollback under CODING-2072.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

