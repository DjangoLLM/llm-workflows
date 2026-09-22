# Agent Notes

## Product direction and planning context

- Read `spec/VISION.md` for product direction and `CONTEXT.md` for canonical terminology. Read `spec/README.md` to identify active specs and follow the spec lifecycle.
- Legacy planning documents are compressed in `docs/archive/legacy-specs-2026-09-22.tar.gz`; see `docs/archive/README.md` for recovery. They are historical references, not current requirements, an approved roadmap, or instructions to resume old work. Do not extract them into the working tree as routine context.
- Do not load muted planning documents as routine context or implement their outstanding tasks. Consult them only when the user explicitly brings them into scope or a specific implementation question requires historical evidence; reading them does not reactivate them. User instructions take precedence over the registry.
- New implementation specs must be listed as active in `spec/README.md`. Reactivating a legacy spec requires explicitly selecting it with the user and reconciling it with the current vision.
- Muting planning documents does not deprecate source code, tests, migrations, runtime documentation, or repository instructions. Inspect those as needed to establish actual behavior.

## Spec completion and retirement

- Treat implementation specs as temporary work plans. At completion, verify the implemented scope and required checks, and move lasting public contracts, usage instructions, terminology, and decision rationale into maintained documentation or tests as appropriate.
- Delete a completed spec's planning artifacts, matching HTML mirrors, and exclusively owned supporting assets as part of finishing the implementation. Remove its active registry entry and repair references from maintained files. Do not delete shared assets, partial or unimplemented requirements, or product direction documents.
- Before deletion, enumerate exact paths, check for concurrent/uncommitted edits, and verify that the exact document content is recoverable from Git history. If it is not, preserve the files and report retirement as pending until a recoverable copy exists. Do not create commits merely to satisfy this rule unless committing is authorized.
- Scope retirement to the completed work; folder age, muted status, and ticket status alone are not proof of implementation. For partially completed specs, retire only completed sections after preserving a recoverable copy and keep the remaining scope explicit and active.
- Keep ticket review artifacts at their exact paths while design, implementation, or review is open. Retirement happens after implementation verification and any required review, and removes Markdown/HTML counterparts together.

## Implementation and design artifacts

- When changing inference definitions, catalogs, or adapters, adding an evaluator/provider, or implementing managed choice execution, check the [inference split criteria](spec/VISION.md#inference-architecture-and-split-criteria). Record any triggered criterion and the chosen response in the active implementation spec.
- For managed Temporal steps, make sure the `AgentDefinition.result_type` matches the actual payload shape expected by the workflow activity.
- If a workflow activity is declared as returning `dict`, the underlying agent step must return structured data, not a plain string.
- When adding a new LLM-backed pipeline step, prefer an explicit result type or output schema so Temporal does not fail on argument/result decoding.
- For Plane design-doc phases, do not stop at `HLD.md` or `LLD.md`. The doc watcher discovers reviewable HTML artifacts, so create or update the matching `HLD.html` or `LLD.html` in the same ticket design directory whenever producing an HLD or LLD deliverable.
- Keep all user-reviewable design artifacts for a Plane ticket in that ticket's exact `spec/<module>/<ticket>/` directory, with supporting assets below it, so relative references and watcher discovery continue to work.
