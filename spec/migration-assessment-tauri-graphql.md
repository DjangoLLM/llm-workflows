# Moving freedom-agents to the reusable Tauri/GraphQL framework

Assessment date: 2026-09-21.

The migration is feasible, but most of the work is a runtime port. The target supplies persistence, generated APIs, app composition, and desktop/web transports. It does not yet supply the execution capabilities that make up most of freedom-agents.

My recommendation is to preserve Temporal, package freedom-agents as a reusable App, and prove one complete execution path before committing to a language rewrite. Keeping Python for execution is a useful intermediate option. Removing Python entirely means replacing the Pydantic AI agent loop, Python tool implementations, and workflow authoring contracts as well as Django.

## Scope and evidence

“This project” here means the current freedom-agents repository, its examples, and its public integration contracts. It does not include porting every application that consumes it.

I inspected the current working trees, including uncommitted changes:

- Source HEAD: `11862bdc4d8b7f69e3c89907a00a9c7ffa103ce7`.
- Target HEAD: `82f69434109c54dbc456062b146d48fdd7de9dce`.
- Target: `/Users/karthik/.config/ticketry/worktrees/tauri-graphql-template/CODIN-1989-reusable-apps-framework-compose-projects`.

Both trees contain substantial ongoing work. In particular, reusable App composition in the target includes uncommitted files. These commit IDs alone do not reproduce the assessed state. Freeze an integrated revision before implementation.

This is a source-based assessment. I did not run the suites, create a prototype, inspect production data, or exercise live inference. The estimates below are engineering judgments, not measured throughput.

## What actually moves

The inspected model/runtime files total about 3,150 lines, excluding management commands, plugins, migrations, examples, and tests. There are three current Django models plus the step-parent join table. The package has no application routes in `urls.py`; the existing operator interface is Django admin. A React run inspector would be new work.

| Existing responsibility | Target home | Migration work |
| --- | --- | --- |
| `AgentRun`, `PipelineRun`, `PipelineStep`, parent links | One execution Module's SeaORM migrations and generated entities | Preserve UUID identity, JSON payloads, timestamps, indexes, foreign keys, deletion rules, and directed lineage. |
| `Pipeline` and `PipelineStep` | Execution services behind supported host capabilities | Port lifecycle tracking, preprocessing, postprocessing, failure recording, and step dispatch. Keep workflow ordering in Temporal. |
| `AgentConfig`, `Agent`, `ManagedAgent` | Python runner initially, or a new Rust execution library | Preserve typed outputs, backend selection, instructions, tool loops, validation/retries, managed results, and failure behavior. |
| Step, pipeline, and agent-config catalogs | Host-composed execution registrations | Replace Django startup and dotted Python imports with explicit contributions from installed Apps. |
| Temporal plugins, activities, management command | Supervised worker executable and workflow registrations | Preserve names and payload contracts where needed; replace Django bootstrap and configuration. |
| Tool decorators, registry, Pydantic adapters, FastMCP server | Retained Python tool service, or Rust tool runtime and MCP adapter | Port discovery, schemas, validation, exposure rules, error results, and transports. GraphQL is not an MCP replacement. |
| Django signals and callbacks | Internal execution events plus GraphQL subscriptions | Separate required downstream work from disposable UI notifications. |
| Django admin | Optional React module UI | Run list/detail, payloads, failures, filters, step relationships, and live updates. |
| Django package installation | Reusable `app.json` plus thin consumer Project | Preserve reuse across applications rather than embedding execution in one desktop shell. |
| Tests and examples | Contract tests, Rust integration tests, retained Python tests where applicable | Re-express behavior across language boundaries and prove both transports. |

Source anchors: [models](../models.py), [agents](../core/agent.py), [pipeline lifecycle](../core/pipeline_structure.py), [step catalog](../core/step_catalog.py), [Temporal composition](../core/temporal/worker_plugins.py), and [tool registry](../core/tools/registry.py).

## What the target already provides

The supplied checkout uses Rust, SQLite, SeaORM, Seaography, React, Apollo, GraphQL Code Generator, and Tauri. It has a desktop IPC transport and a headless HTTP/WebSocket server. Migrations generate entities and the GraphQL contract; caller operations generate TypeScript types.

Its new App tooling resolves local App sources, composes module registries, qualifies migration identities, and generates frontend exports. This is a good match for freedom-agents' purpose as a reusable package. App installation is currently local-path based, so distributing a versioned execution package also needs a reproducible source/dependency arrangement.

Keep the three execution models and their join table in one Module initially. The target does not yet support cross-module model relations or transactions. Splitting agents and pipelines into separate Modules would introduce that problem immediately.

## Framework gaps that affect the design

### Execution capabilities

The target's `AGENTS.md` restricts authored Module Rust to `crate` and `module_host`. Module manifests have a dependency allowlist. `ModuleCtx` currently offers database access, transactions, and event publication, but no network, subprocess, or Temporal handle.

An execution Module therefore cannot simply import Temporal, an HTTP client, or a CLI driver. Add typed execution capabilities to the host boundary, with their implementations in reusable runtime crates or services. Inject them into both desktop and web hosts. Also provide worker access outside a GraphQL request; a request-scoped `ModuleCtx` alone cannot run background activities.

This is framework work even if inference remains Python.

### Contributions from other Apps

Today's App manifest composes Rust/UI Modules. freedom-agents also needs consuming Apps to contribute workflows, steps, agent configurations, and tools. Define how those contributions register, how duplicate names fail, and how the worker receives the same installed set as the API host.

A pure Rust library imported directly by every Module would violate the current authoring rules. A Python worker is also not automatically packaged or registered by the existing manifest. Either route needs an explicit supported mechanism.

### Data types and protected writes

Prove generation and round trips for UUIDs, arbitrary JSON payloads, nullable values, UTC timestamps, foreign keys, and parent links. The examples do not establish this entire combination. Foreign-key GraphQL relation exposure is explicitly outside the target's proven boundary.

Generated CRUD must not let ordinary callers invent successful runs or overwrite execution outputs. Use the framework's write-selection and hook facilities, with the required documented exception for deviations. Starting a run is a custom command with workflow side effects, not a generated table insert. Keep generated reads where they fit.

The existing models do not have a durable workflow-ID mapping or idempotency key. If the new API starts workflows, add a stable request/workflow identity and recovery for a crash between ledger creation and Temporal acceptance. A database transaction cannot atomically commit a remote Temporal start. An outbox or an equivalent proven reconciliation protocol is additional work.

### Events and lifetime

`ModuleCtx.publish` uses a process-local broadcast channel with a 64-event backlog. Events can be dropped while disconnected or lagging. A separate worker updating a database does not automatically publish into that API process.

Add a worker-to-host event path. Query persisted state after subscription establishment/reconnect using a version or cursor protocol that closes the snapshot race. Required automation should use durable messages or Temporal, not UI notifications. The framework forbids polling as the UI's live-update strategy.

Choose who runs work after the desktop window closes. A worker tied to Tauri cannot continue while that process is absent; Temporal can retain progress and wait for a worker to return. Continuous execution needs a separately supervised worker. A local SQLite ledger also requires its owning host to remain reachable if a remote worker records results through it.

### Desktop/web topology

The template deliberately gives desktop and web separate SQLite stores with no synchronization. Decide whether these are independent installations or two clients for one execution service. The second option requires changing the supplied architecture.

The web host has no authentication or authorization. Public or shared deployment needs identity, row access policy, worker authentication, secret handling, and operational deployment work. This matters especially for agent prompts, tool inputs, and outputs. It is outside the baseline estimates below.

Target evidence is in `crates/module-host/src/module_ctx.rs`, `events.rs`, `custom_ops.rs`, `scripts/check-module-dependencies.mjs`, `packages/framework-cli/src/index.js`, and `docs/stability-boundary.md` under the target path above.

## Three migration paths

| Path | What remains | Result | Rough effort |
| --- | --- | --- | --- |
| Wrap the existing service | Django, Python, Temporal, existing database ownership | New Rust/React application talks to a newly added service API. Useful transition, but not a complete project migration. | 2–4 engineer-weeks |
| Move persistence/API, retain Python execution | Python Temporal workers, Pydantic AI, Python tools | Rust owns the new store and API. Python records lifecycle changes through a versioned service contract. Django can eventually be removed. | 6–10 engineer-weeks |
| Full native port | Temporal service and external provider/CLI dependencies | Rust owns persistence, workflows/activities, agent execution, tools, and MCP. React/Tauri supplies the interface. | 12–20 engineer-weeks |

These assume one engineer comfortable with both stacks, one local/single-user deployment model, a minimal admin replacement, one representative consumer, and a bounded history import. They include testing and both application targets. They exclude migrating all sibling apps, public multi-user hosting, store synchronization, production-scale performance work, and full offline execution. New provider/tool breadth or maintaining the retiring pi bridge can expand the range.

The intermediate path still needs a real refactor. `Agent` reads Django settings; `ManagedAgent` creates and updates ORM rows; pipeline constructors eagerly create records; worker registration depends on Django startup; completion uses Django signals. Move configuration and persistence behind explicit interfaces. A Python process running the unchanged package still requires Django.

Keep one writer responsible for the authoritative ledger. Do not have Django migrations and SeaORM migrations independently manage the same tables. For the intermediate path, prefer Rust-owned persistence with authenticated, idempotent worker commands. A temporary read projection over the old service is a different transition design and needs its own synchronization rules.

For the native path, Rust types and JSON Schema can express the new contracts, but Python `BaseModel` subclasses, custom validators, arbitrary Python callables, and `extra_kwargs` do not translate automatically. Inventory and port each supported behavior. Do not equate a successful provider call with replacing Pydantic AI's multi-turn execution and repair loop.

Temporal itself can remain. As checked for this assessment, the official Rust SDK has a published [1.0.0 release dated 2026-09-04](https://docs.rs/crate/temporalio-sdk/1.0.0), and its [upstream documentation](https://github.com/temporalio/sdk-rust/blob/main/crates/sdk/README.md) covers workflows, activities, workers, and history replay. This makes a native route credible. It does not prove compatibility with this framework's exact dependency pins or with existing Python workflow histories; both require experiments.

## Suggested sequence and acceptance gates

1. **Freeze scope and revisions.** Decide native versus retained Python, which backends survive, and whether both targets are independent installations. Capture a tested source/target baseline and one real consumer contract.
2. **Spend 3–5 days on a complete-path experiment.** Install an execution App into a fresh Project; generate its schema with all four tables; start a two-step workflow through a custom mutation; execute one code step and one typed inference step; persist results; deliver a subscription update. Run it through desktop and web. Use a minimal host capability rather than bypassing Module rules.
3. **Prove failure behavior before expanding.** Kill/restart the worker; retry an activity; reject malformed structured output; disconnect/reconnect the UI; repeat the start request. Verify no lost terminal state, duplicate logical start, or silently changed decision. Record physical attempts separately from logical step identity.
4. **Port the reusable contracts.** Implement runtime contributions, configuration, lifecycle commands, tool schemas, backend dispatch, process cleanup, and a replacement for required signal consumers. Preserve structured activity results, including the repo rule that a `dict` activity receives an object rather than a JSON string.
5. **Move consumers and data.** Port one external toolset and one host workflow before declaring the package reusable. Import history with preserved UUIDs and relationships. Verify row counts, canonical payload comparisons, and deletion semantics against a source snapshot.
6. **Cut over new work.** Prefer letting old workflows finish on old workers and sending new workflows to versioned types/queues. Do not route old histories to rewritten Rust workflows without replay proof. Keep rollback explicit: history import does not migrate Temporal history, and new writes after cutover cannot be discarded during rollback.
7. **Complete delivery checks.** Run generated drift, module seal, Rust/TypeScript checks, API and transport tests, real Temporal recovery tests, MCP transport tests, and live inference for the selected backend. Verify worker shutdown and packaging separately for each target.

The first experiment is the decision point. If execution capability injection and typed payload generation require extensive framework changes, finish those before porting the rest of the library.

## Existing work and consumer impact

The checked-in runtime still supports `pydantic_ai` and `pi_worker`. [Story 2042](freedomagents--29a8b724/T2042--remove-the-temporal-pi-worker-inference/SPEC.md) specifies removing the pi bridge. [Story 2055](freedomagents--29a8b724/T2055--i-wanna-add-codex-appserver-as-one-of-th/SPEC.md) specifies typed Codex CLI inference and explicitly defers app-server. Neither specification is evidence that the change has shipped. Choose the intended baseline before spending time porting a retiring backend.

The existing [framework review](reviews/2026-09-21-framework-review.md) is useful input, but some findings already have working-tree fixes. For example, preprocessing now runs inside the step failure handler, and an uncommitted migration squash provides a new standalone path. Recheck findings rather than carrying their previous status into the new implementation. The project [vision](VISION.md) also describes recovery guarantees that are goals, not all current capabilities.

A limited sibling-source scan found consumers in `research-agent` and `freedom-plane-agent`. Research tools import the current ToolSet/registry API. Plane code imports agent execution and Temporal plugin APIs, including a legacy path. This establishes consumer migration work; it does not establish that those consumers currently run against this exact checkout. A Rust port is a breaking change for Python consumers unless an adapter remains.

The practical next investment is the complete-path experiment, followed by a revised estimate using its results. Porting the database alone would leave the principal execution risks unanswered.
