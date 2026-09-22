# Planning context and spec lifecycle

## Maintained product documents

- [VISION.md](VISION.md) records the workflow-building goal, target primitives, and execution principles. Its [target application structure and authoring process](VISION.md#target-application-structure-and-authoring-process) guides future library alignment.
- [CONTEXT.md](../CONTEXT.md) defines the agreed domain language.
- This index records active work and the lifecycle of implementation specs.

These documents persist as the product evolves. They are not disposable implementation specs.

## Active specs

None.

When work is selected, add an entry here with the exact spec or ticket directory, its scope, and its status: design, implementing, verifying, or retirement pending. Activating a spec does not activate its parent folder or sibling tickets.

## Muted planning documents

The 89 legacy planning files previously under `spec/` are compressed in [the legacy archive](../docs/archive/legacy-specs-2026-09-22.tar.gz), including previous migration proposals, ticket designs, implementation plans and drafts, research plans, and reviews. Archival does not establish that their proposed work was implemented.

See [archive recovery instructions](../docs/archive/README.md) for historical lookup. Do not extract the archive into the working tree as default agent context or treat it as a backlog or authority over the current vision. Consult a specific document only when requested or when needed to answer a concrete historical question. To resume a legacy proposal, select it with the user, reconcile it with the current direction, and register its exact scope above.

The original legacy files have been removed from `spec/`, so directory scanners no longer encounter their loose Markdown and HTML artifacts there. External watcher configuration has not changed. Source code, tests, migrations, and runtime documentation remain available as evidence of actual behavior.

## Lifecycle for new work

1. Register the selected scope under Active specs. For Plane tickets, keep all reviewable documents and assets in the exact `spec/<module>/<ticket>/` directory. Produce matching HTML artifacts when producing HLD or LLD deliverables, as required by the repository instructions.
2. Implement and verify against the active spec. Keep unresolved requirements explicit; partial completion does not retire the whole spec.
3. Preserve lasting knowledge in maintained documentation and tests. Update the vision or glossary when the agreed product model changes. Keep instructions required to operate or extend the implemented capability outside disposable planning artifacts.
4. Confirm the scope is implemented, required checks pass, and any required review is complete. Identify the precise spec files, mirrored review artifacts, and exclusively owned assets to retire. Check references and local changes before deletion.
5. Verify the exact content to be removed is recoverable from Git history. Untracked files and uncommitted revisions do not qualify merely because an older file exists in Git. If recovery is not established, mark the entry retirement pending and keep the content until it is preserved through the authorized commit workflow.
6. Delete the verified completed planning artifacts and repair maintained references in the implementation's closing change. Remove the active entry when retirement is complete. Include the retired paths and recovery commit in the implementation handoff or commit/PR description. Use Git history for routine retirement; the compressed legacy archive is a one-time cleanup, not a growing archive of future completed specs.

Retirement is part of completing work, not a timed cleanup job. Nothing is deleted merely because it is old or muted. When a completed portion shares a document with unfinished work, preserve the original in history, remove the completed planning sections, and leave the remaining scope registered.

The agent performing implementation follows this checklist through `AGENTS.md`. Automatic cleanup tooling and watcher filtering are not implemented by this policy.
