# Remove the Temporal pi-worker inference backend

Story CODING-2042 · Implementation specification · 2026-09-21

## Problem Statement

Application developers currently have two inference backends to configure and maintain. The pi-worker backend sends every model turn through Temporal to a TypeScript worker, although Pydantic AI already owns the agent loop, tool execution, and output validation. This adds queue dependencies, translation code, latency, and failure modes to ordinary agent execution.

## Solution

Use direct Pydantic AI inference for every Agent. Remove the per-turn Temporal inference transport and its pi-specific code, configuration, registrations, and demos. Preserve ordinary MCP tool exposure and Temporal pipeline orchestration. A Temporal pipeline activity may still run a managed Agent that invokes its provider directly.

## User Stories

1. As an application developer, I want an Agent with default configuration to call its provider directly, so that inference needs no TypeScript worker.
2. As an application developer, I want explicit direct-backend configuration to remain valid, so that existing direct callers keep working.
3. As an application developer, I want unsupported backend values rejected during configuration, so that a legacy request cannot silently select a different backend.
4. As an application developer, I want string model names and supplied model objects to retain their current behavior, so that this removal does not change model selection.
5. As an application developer, I want model settings and instructions forwarded as before, so that the configured agent behaves consistently.
6. As a tool author, I want registered toolsets resolved through the existing registry adapter, so that my tools remain callable by the model.
7. As an application developer, I want explicitly supplied tools to remain available, so that tool registration is optional.
8. As an application developer, I want structured results validated by Pydantic AI, so that consumers receive the declared output type.
9. As an async caller, I want to await Agent execution, so that it fits my application lifecycle.
10. As a synchronous caller, I want the existing synchronous execution API, so that I need not adopt an async entry point.
11. As a pipeline author, I want managed run persistence and lifecycle activities preserved, so that removing an inference backend does not disrupt pipeline tracking.
12. As an MCP client author, I want exposed registry tools to remain discoverable and callable, so that existing integrations keep working.
13. As an operator, I want stdio, HTTP, and SSE MCP transports preserved, so that the removal does not alter deployment choices.
14. As a maintainer, I want pi-specific workflow and activity registrations removed, so that workers do not advertise unavailable inference capabilities.
15. As an operator, I want no inference queue dependency or pi-specific setting, so that ordinary Agent execution only requires its configured provider.
16. As a maintainer, I want obsolete demos and documentation removed or updated, so that users cannot follow unsupported examples.
17. As a maintainer, I want deterministic regression coverage, so that direct inference, tools, and structured output can be verified without external services.
18. As a reviewer, I want historical design records clearly distinguished from active instructions, so that retained history does not imply backend support.

## Implementation Decisions

1. Retain the AgentConfig execution\_backend field as a single-value compatibility field accepting only pydantic\_ai, which remains its default. Any other value raises ValueError during configuration, before provider construction, tool resolution, or network activity. The error identifies execution\_backend and the sole supported value. This includes the removed pi\_worker value and arbitrary invalid values.
2. Apply the same validation when Agent builds a configuration from keyword arguments. Preserve the existing explicit-config and default-settings entry points. Do not silently drop a backend argument while constructing a configuration.
3. Remove backend branching from model construction. Preserve the current direct behavior: string names construct an OpenAIResponsesModel; an omitted model selects gpt-5-mini; supplied model objects pass through; configured settings pass through, otherwise the existing reasoning-effort default applies. This is not a provider expansion or a model-default change.
4. Preserve instructions, explicit tools, registry toolset resolution, extra keyword forwarding for the direct path, and result\_type mapping to Pydantic AI output\_type. Preserve existing async/sync return conventions and ManagedAgent persistence and signals.
5. Delete PiWorkerModel, its public export, per-turn workflow dispatch, message/schema/tool/result translation, the inference routing stub, the inference queue constant, and pi-specific settings and option extraction. Do not create aliases, compatibility shims, or an alternative inference transport. Old pi-specific extra options are unsupported and must not be consumed as backend routing options.
6. Remove the inference workflow from the core worker plugin. Preserve pipeline lifecycle activities, generated step activities, worker composition, and workflow execution helpers. Shared Temporal connection and queue settings remain where pipeline orchestration requires them.
7. Remove the pi-only MCP bridge, its Temporal wrapper activities, and their plugin registrations as one unit. Repository inspection found only the pi demos invoking that chain. Recheck consumers at implementation time; if an independent non-demo consumer has appeared, preserve the bridge needed by that consumer and document the evidence. Do not remove general MCP support to satisfy the pi cleanup.
8. Preserve the MCP server, MCP adapter, transport runner, management command, registry exposure and safety checks, FastMCP dependency, and ordinary MCP smoke example. Preserve stdio, HTTP, and SSE behavior.
9. Delete or update the pi inference, pi agent, pi bridge, and pi MCP-loop demos and their explainer. Preserve shared feedback-demo functionality and ordinary MCP examples. Remove imports that would otherwise refer to deleted symbols.
10. Keep historical design artifacts as records rather than rewriting their original decisions. They are not current runtime documentation. New removal specifications necessarily name deleted symbols; those references are intentional design context. Active examples and documentation must describe only supported behavior.
11. No database schema, migration, persistence format, or new dependency is required. The external TypeScript worker is outside this repository; this change removes the repository's expectation of that service without modifying or deleting external deployments.
12. This is an immediate removal, with no deprecation period or fallback. Existing applications selecting the removed backend must switch to the direct configuration and supported provider settings. The implementation does not operate on in-flight external workflows. Operators must account for outstanding old inference runs before deploying a worker that no longer registers their workflow.

## Testing Decisions

Use existing public interfaces and assert observable behavior. The primary seam is Agent.run and Agent.run\_sync with a deterministic Pydantic AI model. Retain the real Pydantic AI agent loop, registry adapter, tool invocation, and output validation; substitute the model response boundary to avoid provider credentials, a Temporal server, and the TypeScript worker. No new production injection interface is needed because AgentConfig already accepts model objects at runtime.

| Contract                        | Required evidence                                                                                                                                                                                                                                                  |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Sole supported backend          | Default and explicit pydantic\_ai configurations work. Removed and unknown backend values fail through AgentConfig and the Agent kwargs entry point before model construction.                                                                                     |
| Model configuration             | Verify omitted model, string model, supplied model object, configured/default settings, and instruction forwarding. Use constructor spies where provider creation would otherwise require credentials.                                                             |
| Tool loop and structured output | A deterministic model requests a registered tool, receives its result, and then returns an output validated against the configured result type. Assert the tool's observable call and typed result. Exercise async and sync entry points.                          |
| Explicit tools                  | An explicitly supplied callable remains callable through the direct agent loop.                                                                                                                                                                                    |
| Output validation               | Invalid structured output cannot escape as a successful typed result; verify the existing Pydantic AI validation/retry or terminal-error behavior without imposing a new retry policy.                                                                             |
| No inference transport          | Direct execution succeeds without a Temporal client or pi worker; instrument the client connection boundary to fail if inference attempts to connect.                                                                                                              |
| Managed execution               | Existing persistence success/failure and signal tests continue passing. Keep result schemas compatible with managed activities declared to return dictionaries.                                                                                                    |
| Worker composition              | The core plugin still registers pipeline activities and composes successfully; removed inference and pi bridge registrations are absent.                                                                                                                           |
| MCP compatibility               | Existing adapter, server, registry exposure, tool error, and management-command tests pass. Exercise the ordinary MCP STDIO smoke test where dependencies are available. Verify HTTP/SSE argument forwarding and port validation at the existing runner interface. |
| Removal completeness            | Search tracked runtime code, examples, active docs, configuration, and imports for removed symbols and queue names. Classify every remaining match.                                                                                                                |

Prior art includes the Agent constructor and async/sync tests, MCP in-process echo and tool-error tests, registry exposure tests, core plugin and worker composition tests, and workflow-helper and pipeline activity suites. Expand these existing suites rather than testing private translation helpers that are being deleted.

Run focused regression tests first, then the normal repository suite. Report failures and unavailable live-service checks separately; a passing mock suite is not evidence of a completed live transport check. Generated coverage snapshots and caches are not runtime references. Tests that explicitly reject a removed value or assert a registration is absent may name the removed symbols; these are regression assertions, not stale support. The required search has zero unexplained runtime matches, with explicit exceptions for historical/current design records and negative regression assertions.

## Out of Scope

* Removing Temporal pipelines, managed run persistence, pipeline lifecycle activities, or shared Temporal configuration.
* Removing the MCP server, registry exposure, adapters, transport support, or FastMCP dependency.
* Redesigning provider selection, changing default models, adding a new backend, or changing Pydantic AI's tool loop and retry policy.
* Editing external TypeScript services, cancelling deployed workflows, or changing other repositories.
* Creating implementation tickets or implementing this specification during the Spec stage.

## Further Notes

The Ideas assessment inspected repository HEAD 11862bd and found no attachments, external links, or dependency blockers on the Story. The Story contains the detailed source-file inventory and consumer-search evidence. This specification makes the compatibility-field choice explicit and resolves the search criterion's necessary exceptions for rejection tests and design records.

During Spec, additional working-tree edits appeared in the model adapter, Agent tests, and generated coverage. These were not made by this stage. Recheck the working tree and bridge consumers when implementation begins, and preserve unrelated work. Separate stories concerning defects in the backend may overlap code scheduled for deletion; this specification does not close or modify those stories.

All artifacts for this Story belong in its supplied design directory. SPEC.md is authoritative; SPEC.html is its reviewable rendering. No HLD or LLD is produced at this stage.