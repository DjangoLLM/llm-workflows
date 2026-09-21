# 11. Resume a Temporal agent across recorded turns and tool activities

## Parent

CODING-2069. See [implementation specification](../SPEC.md).

## What to build

A worker restart resumes a multi-turn agent using completed Temporal activity results rather than restarting its conversation.

## Acceptance criteria

- [ ] Schedule individual inference turns and tools separately and use the same pure transition logic as direct execution.
- [ ] Preserve invocation/turn keys, schema versions, counters, and transcript.
- [ ] Disable automatic retry for unsafe tools; exercise bounded read-only/idempotent retries.
- [ ] Restart after a completed turn/tool, assert no repeat of recorded work, and replay a captured history.

## Blocked by

- Draft 10: Run a Rust code-and-agent workflow on Temporal under CODING-2069.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

