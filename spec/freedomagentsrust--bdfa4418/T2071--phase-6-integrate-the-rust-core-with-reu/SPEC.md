# Phase 6: Integrate the Rust core with reusable Apps, GraphQL, and MCP

CODING-2071 · Implementation specification · 2026-09-21

Pure Rust execution only. SQLite is the initial execution ledger; Temporal remains an external service with Rust workflows and activities. No Python or JavaScript execution workers, CLI inference backend, or product UI is required. Phase 5 is the core-working milestone. Later database backends, public multi-user hosting, and store synchronization are deferred.

## Problem statement

The proven core is not yet available to composed framework Apps or external clients. Current Module capabilities do not expose background execution, and process-local subscription notifications cannot recover missed worker events.

## Solution

Install the core as a reusable App, compose its runtime registrations, expose protected GraphQL commands/read models, and serve permitted tools over Rust MCP. Keep all execution headless and preserve the framework's generation boundary.

## User stories

1. As an App author, I want to contribute steps and tools through the supported framework, so that I do not bypass module rules.
2. As an Project author, I want to install two contributing Apps, so that worker and API see the same catalog.
3. As a client author, I want to use generated GraphQL reads, so that contracts match persisted models.
4. As a caller, I want to start and control a run through explicit commands, so that I cannot corrupt lifecycle state.
5. As a subscriber, I want to receive separate-worker changes, so that live views follow committed work.
6. As a subscriber, I want to resume from a cursor, so that disconnects do not hide completed work.
7. As an MCP client, I want to discover permitted Rust tools, so that I can invoke the same contracts.
8. As a tool owner, I want to keep private tools unexposed, so that registration does not imply public access.
9. As an operator, I want to stop transports cleanly, so that subscriptions and tool tasks release resources.
10. As a maintainer, I want to test web and desktop Rust transports, so that integration does not require a new product UI.

## Implementation decisions

1. Create one reusable execution App with the ledger Module and optional transport contributions. Use the framework's generated App/Module registries. The API host and worker consume the same resolved installation identity and definition versions.

2. Extend the supported module-host vocabulary with typed execution registration and command handles. The host provides concrete Rust implementations. Modules continue to name only sanctioned crate roots; no arbitrary Temporal/HTTP imports or dependency-allowlist widening as a shortcut.

3. Prove contributions from two fixture Apps at generation/startup, including duplicate names, missing definitions, source relocation, and mismatched catalog versions. Composing Apps must not require a Module to reference another Module's entity types.

4. Retain generated ledger reads with pagination/filtering where safe. Suppress public generated mutations for runtime-owned ledger Models using supported write-selection and a documented exception; clients use explicit start/cancel/retry/reconsider/resolve commands carrying stable request IDs and expected revisions.

5. Expose only the minimum client-visible error categories and redacted configuration. Credentials never enter entities or the schema. Execution payloads remain sensitive local data; public/shared deployment and authorization are deferred, so the HTTP listener remains loopback-only.

6. Add an append-only change record with a monotonic cursor in the same transaction as each accepted lifecycle mutation. A Rust local notification channel wakes the API host after commit; the API reads the durable change log to recover gaps. Notification loss cannot erase a committed change.

7. Expose a versioned snapshot and changes-after-cursor protocol. Establish the subscription before snapshot delivery and drain committed changes beyond the snapshot watermark without a race. Clients deduplicate by cursor/revision. An expired cursor yields an explicit snapshot-required result rather than silently skipping data.

8. Support a separate local worker through authenticated local IPC or a same-host owned channel, with connection/reconnect catch-up. No client polling or focus-refetch loop is the live strategy. Background change-log delivery/reconciliation is allowed and must be bounded and testable.

9. Serve MCP from a Rust executable over STDIO initially, using the shared tool registry and validators. Advertise only explicitly MCP-exposed tools; reject invalid arguments before invocation and return protocol-appropriate tool failures. Framework run controls are not automatically exposed as arbitrary tools.

10. MCP direct calls to mutating tools require an explicit invocation key and the same durable effect service/policy as the core; unsafe direct invocation is rejected. Discovery must not expand agent tool authorization. HTTP/SSE MCP parity is deferred from this initial release.

11. Verify the same GraphQL behavior through headless HTTP/WebSocket and Tauri Rust transport boundaries. Generated TypeScript contract checks may run as development checks, but no JavaScript execution worker or React screen is part of this delivery.

## Testing decisions

- Install two fixture Apps in a clean consumer Project, generate contracts, and use public commands to execute a real core workflow. Assert catalog agreement and rejection of invalid contributions.

- Probe generated schema and runtime behavior to ensure arbitrary create/update/delete cannot fabricate run outcomes; exercise command idempotency and stale revision rejection.

- Run separate worker/host processes, interrupt notifications and subscriptions, then verify snapshot/cursor catch-up without gaps or duplicates in client state. Include a reconnect during snapshot acquisition.

- Drive actual MCP initialization/list/call over STDIO, schema/argument checks, exposure filtering, structured failure, mutation-key enforcement, and cleanup on disconnect.

- Run target generation/drift/seal verification and both Rust transport suites. Prior art: composed-schema custom operation tests, live subscription tests, and existing MCP adapter/server behavior.

Tests assert observable outcomes at the public Rust, workflow, or transport boundary. Do not mirror private helper implementations. These are delivery requirements; no runtime acceptance was executed while authoring this specification.

## Out of scope

React operator UI, public HTTP hosting/authentication, cross-device store synchronization, remote SQLite workers, HTTP/SSE MCP, and automatic exposure of every framework control.

## Further notes

Depends on: CODING-2070. Preserve the existing phase dependency edges. Implementation children refine this scope; they do not reopen the pure Rust/SQLite decision.

The prior migration assessment and source-project vision informed this specification. Existing Python tests supply behavioral prior art, not a runtime dependency. The baseline checkouts contain uncommitted work; implementation must record integrated revisions and preserve unrelated edits.

SPEC.md is authoritative; SPEC.html is its reviewable rendering. The full specification is also published on the Story. Any later change to a shared execution contract must update affected dependent specifications before their implementation.

