# Add typed inference through the Codex CLI

Story CODING-2055 · Implementation specification · 2026-09-21

## Problem statement

Application developers need to call Codex with a declared response type and consume a validated value through the existing Agent API. The installed coding-agent driver can pass an output schema to Codex, but the framework does not connect this capability to AgentConfig.result\_type. Callers would have to generate schemas, manage processes, extract responses, and validate output themselves.

## Solution

Add a codex\_cli execution backend. A caller supplies instructions, an input payload, and a Pydantic response model through AgentConfig. The backend derives a JSON Schema, runs Codex once, and returns a result whose output is an instance of that model. Managed execution persists the same value as JSON-compatible data.

The user chose CLI-based typed inference after considering app-server. App-server is deferred. Live Codex inference is a mandatory implementation acceptance check, explicitly requested by the user; deterministic substitutes alone cannot satisfy acceptance.

## User stories

1. As an application developer, I want to select Codex through AgentConfig, so that I use the existing Agent entry points.
2. As an application developer, I want to declare a Pydantic response model, so that response fields have a concrete contract.
3. As an application developer, I want the framework to generate the schema, so that I do not maintain a separate schema file.
4. As an application developer, I want nested models, arrays, scalar fields, enums, and nullable fields, so that ordinary structured decisions fit the response contract.
5. As an application developer, I want unsupported schemas rejected before inference, so that my request cannot silently lose constraints.
6. As an async caller, I want to await Agent.run, so that inference fits my asynchronous application.
7. As a synchronous caller, I want Agent.run\_sync, so that I can use Codex in existing synchronous integrations.
8. As a caller, I want the validated value in result.output, so that consuming a Codex result resembles consuming an existing Agent result.
9. As a caller, I want only the final response parsed, so that progress messages and tool output cannot contaminate my result.
10. As a caller, I want invalid JSON or invalid values to fail, so that malformed decisions do not drive pipeline branches.
11. As a caller, I want to select a Codex model or use its configured default, so that model choice is explicit when needed.
12. As an operator, I want existing Codex authentication to work, so that the framework does not require a second credential configuration.
13. As an operator, I want a deadline for the whole CLI invocation, so that a process stuck while producing output cannot run indefinitely.
14. As an async caller, I want cancellation to stop and reap the process, so that abandoned requests do not keep running.
15. As an operator, I want per-call temporary files removed, so that requests do not leave schema and response files behind.
16. As a pipeline author, I want managed success and failure records to preserve their current behavior, so that Codex inference participates in existing tracking.
17. As a pipeline author, I want structured persisted output compatible with my activity return shape, so that Temporal decoding succeeds.
18. As a maintainer, I want unsupported tools and settings rejected explicitly, so that configuration does not appear to work while being ignored.
19. As a maintainer, I want other inference backends unaffected, so that adding Codex does not change existing callers.
20. As a reviewer, I want real Codex inference evidence, so that tests prove the transport and schema work with the supported CLI.

## Implementation decisions

1. Add codex\_cli to execution\_backend and preserve pydantic\_ai as the default. Support explicit AgentConfig, Agent keyword arguments, and configured defaults consistently. Backend validation must occur before process launch. Coordinate with Story #2042, which removes pi\_worker: preserve it only while it remains in the integration base; never restore it after removal. That story's single-backend assertions must become compatible with this deliberate addition.
2. Introduce a Codex runner behind Agent's execution dispatch. Keep the existing Pydantic AI runner for its current backends. Both expose asynchronous and synchronous execution returning an object with output. Do not force CLI execution into a Pydantic AI per-turn model adapter or claim support for its full conversation API. The Codex result contract guarantees output only; message history and Pydantic AI usage methods are outside this release. Update managed-run label lookup so it does not assume every runner is a Pydantic AI Agent.
3. For this release, require result\_type to be a Pydantic BaseModel subclass with a fixed object shape. Supported field schemas are strings, integers, numbers, booleans, null, enums, arrays with one item schema, nested fixed objects, local nonrecursive references, and nullable unions of one supported type with null. Require every declared field in the wire schema, including fields with Python defaults; nullable fields still appear explicitly. Set additionalProperties to false for every fixed object. Python model definitions must not allow arbitrary extra fields. Validate the final JSON against the original model using strict JSON validation, including custom validators. Preserve aliases consistently between schema generation and validation.
4. Reject omitted result\_type, bare dict, arbitrary-key mappings, Any, scalar roots, RootModel, dataclasses, non-nullable unions, recursive references, and schema constructs outside the supported subset before launching Codex. Report the unsupported type or schema location. Strip only schema annotations such as titles, descriptions, and defaults when needed; never discard validation constraints to force compatibility. Field constraints outside the supported subset fail explicitly. A caller needing dictionary persistence should use a fixed Pydantic response model and consume its managed JSON representation. This is a bounded initial type contract, not a promise to support every type accepted by other backends.
5. Keep model optional. A nonempty string becomes the CLI model argument; None lets Codex choose its configured default. Reject model objects for this backend. Add only two backend options through extra\_kwargs: codex\_working\_dir, defaulting to the current directory, and codex\_timeout\_seconds, a positive finite number defaulting to 300. Validate directory existence before launch. Reject unknown options, nonempty tools or toolsets, and supplied model settings for codex\_cli. The direct Pydantic AI path retains its current options and tools.
6. Reuse CodexCLIWrapper and extend its explicit execute/build-command options for model selection and output\_last\_message. Its current CodingAgent.run protocol cannot accept schema-specific arguments; use execute for this adapter. Make a fresh wrapper for each call to avoid shared session state. Do not use resume, a shared conversation, or transparent retries. Combine instructions and JSON-serialized input with clear delimiters, pass the prompt through stdin using the supported stdin prompt argument, and keep it out of command-line logs.
7. Use JSONL events for diagnostics and a per-call final-message file as the authoritative response. Pass both output\_schema and output\_last\_message to the CLI. Do not parse CLIResponse.final\_output: the current shared collector concatenates content from multiple events. Require zero exit status and no terminal failure event before reading the final file. Missing, empty, non-UTF-8, malformed JSON, refusal text, and schema-invalid content are failures. Do not recover by finding JSON in commentary or stripping Markdown fences.
8. Keep schema and final-message files in a private unique temporary directory, use absolute paths, and remove the directory on success, launch failure, process failure, validation failure, timeout, and cancellation. The final file must not exist before the invocation, preventing stale-response reuse. Concurrent calls must not share files or driver instances. Cleanup follows process termination so a surviving process cannot recreate an output file.
9. Reuse the existing NonInteractivePolicy type with interactive\=false, allow\_writes\=false, auto\_approve\=false, and stream-JSON output. The current driver maps auto\_approve\=true to a legacy full-auto flag that is absent from the installed CLI help; do not use that default. Keep the explicit read-only sandbox and never enable bypass flags. This limits workspace writes but is not a guarantee that Codex cannot read local files or invoke tools enabled by its environment. Run under the operator's trusted Codex configuration and document that boundary. Bridge-free typed inference does not expose framework tools to Codex.
10. Fix process lifecycle handling in the shared driver, where the process handle already belongs. Apply the deadline across subprocess startup, stdin delivery, concurrent stdout/stderr draining, and process exit. On timeout, cancellation, or reader failure, stop the owned process, await its exit, and close/cancel stream tasks before propagating the original failure. Do not merely wrap the existing execute call in a timeout: today it can leave the child running. Preserve cancellation as cancellation for async callers. Regress other drivers because they share this lifecycle code.
11. Use clear exception categories for configuration/schema rejection, launch or execution failure, timeout, and response validation. Keep the original exception as the cause where applicable. Do not include prompts, raw responses, or credential-bearing stderr in persisted error messages. Existing ManagedAgent execution continues recording FAILED and emitting terminal notifications for execution errors; configuration rejection before a run is created remains a configuration error. No automatic second inference on invalid output; workflow-level retries remain explicit.
12. Preserve ManagedAgent's JSON-safe serialization and existing lifecycle/signals. A successful direct call returns a model instance in output; managed synchronous execution returns the persisted dictionary. Activities declared to return dict must receive that dictionary, not a model instance or JSON string. No database migration, new Temporal inference transport, or new managed cancellation API is required.
13. Driver changes are part of the delivery dependency, not functionality already present. Coordinate them in coding-agent-drivers, release or otherwise make the required revision installable, and verify freedom-agents against that revision. Do not claim delivery based solely on an editable sibling checkout. Keep driver lifecycle and new command-option tests with that package, and framework integration tests with this package.

## Testing decisions

Test observable behavior at Agent.run, Agent.run\_sync, and ManagedAgent. Use a fake executable at the subprocess boundary for deterministic integration coverage, exercising the real schema files, argument forwarding, stdin, output files, and cleanup. Avoid a new public injection API just for tests. Follow the existing Agent async/sync tests, managed persistence and terminal signal tests, and coding-agent driver command/execution tests.

* Configuration: default direct inference remains unchanged; codex\_cli accepts explicit configuration and keyword construction. Unsupported types, tools, settings, model objects, directories, timeout values, and unknown options fail before a subprocess starts.
* Typed success: nested models, arrays, enums, nullability, aliases, and Python defaults produce the declared model through both async and sync entry points. Verify the fake executable sees the actual generated schema, selected model, stdin prompt, and final-message destination.
* Response isolation: emit commentary and unrelated JSONL messages before a valid final file. Only the final file is validated. Earlier valid content must not rescue a missing or invalid final response.
* Failures: nonzero exit despite a valid-looking final file, terminal failure event, missing binary, empty file, malformed JSON, wrong field types, missing fields, and custom validation failure never return successful typed results.
* Resource lifecycle: test a process that keeps stdout open, a process stuck reading stdin, and one that closes stdout but does not exit. Each must respect the deadline. Cancellation must stop and reap the process. Assert cleanup on every exit path and isolation between concurrent calls.
* Persistence: successful managed execution stores a JSON object; execution and validation failures store FAILED and send the expected terminal signal. An activity expecting dict receives a dictionary. Existing direct backend and applicable driver regression suites pass.

Live acceptance is mandatory. Run the implemented backend against an authenticated real Codex CLI with an explicit supported model or a recorded configured default. Exercise async and sync Agent calls and at least one managed call. Request a small fixed nested Pydantic model containing a literal marker, an integer, a list, and a nullable field. Assert the returned Python type and values, managed JSON output and success state, and temporary-file cleanup. This check must use real inference, the installed required driver revision, and the generated schema, not a prerecorded CLI response.

Record the test command, CLI and driver versions, selected model, test result, and a nonsensitive example of the validated result in implementation evidence. If authentication, model access, or the CLI is unavailable, report live acceptance as blocked and do not mark implementation complete. Passing mocks or a skipped live test cannot substitute. Credentials are supplied through the existing Codex environment; never commit them. A live check is required at delivery, while ordinary unit runs remain deterministic and credential-free.

## Out of scope

* Codex app-server, persistent threads, session resumption, and public streaming APIs.
* A framework tool bridge, arbitrary Python return types, arbitrary-key dictionaries, and full Pydantic AI result-object compatibility.
* Changing existing direct-provider behavior, adding fallback providers, or automatic schema-repair inference.
* Removing pi\_worker in this story, changing pipeline orchestration, database migrations, or changing other tickets' workflow states.
* Implementation code and implementation tickets during this Spec stage.

## Further notes

The agreed user-facing contract is typed CLI inference. The bounded schema subset, runner dispatch, final-file extraction, and lifecycle fixes above are specification decisions derived from the inspected implementation. No prototype or live inference was performed during Spec.

The installed codex-cli 0.155.1 help confirms output-schema, output-last-message, model selection, stdin prompts, and the read-only sandbox. It does not list full-auto. The existing driver accepts a schema path but does not yet forward model selection or a final-message path. Its timeout currently starts after stream draining, and its shared output collector combines messages. These findings make a driver update necessary.

The official [Codex non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) describes output-schema for structured responses and output-last-message for the final message. The exact installed CLI version must be rechecked during implementation and exercised by the required live acceptance test.

The project vision assigns validated structured decisions to Agents and execution/recovery policy to workflows. This feature follows that separation. The #2042 specification overlaps Agent backend dispatch; reconcile that change at integration instead of preserving obsolete pi-worker support. Existing unrelated working-tree edits must be preserved.

The user confirmed the public test boundaries and strengthened the live check from optional to mandatory. SPEC.md is authoritative and SPEC.html is its reviewable mirror. No HLD or LLD is produced in this stage. The requested ready-for-agent label is not exposed by the available WorkTracker tools; the Story's transition to Tickets records specification readiness without claiming a label update.