# 20. Expose permitted Rust tools over MCP STDIO

## Parent

CODING-2071. See [implementation specification](../SPEC.md).

## What to build

An MCP client discovers and invokes the same validated Rust tools through the native runtime.

## Acceptance criteria

- [ ] Use the shared tool registry, schema source, and exposure metadata.
- [ ] Reject private tools/invalid arguments and return structured tool failures.
- [ ] Mutating tools require invocation keys and the core durable-effect policy; unsafe direct execution is refused.
- [ ] Real STDIO initialize/list/call/disconnect tests cover cleanup; HTTP/SSE MCP remains deferred.

## Blocked by

- Draft 18: Start and control workflows through protected GraphQL commands under CODING-2071.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

