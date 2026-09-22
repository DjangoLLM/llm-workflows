# Public authoring package layout

Status: retirement pending. Implementation and verification complete.

Expose `AgentDefinition` from `agents.inferences.agents`, `ChoiceDefinition` from
`agents.inferences.choices`, tool contracts from `agents.tools`, `Step` from
`agents.steps`, and `Workflow` from `agents.workflows`. Replace the former
`definitions` package and migrate repository imports and examples.

Keep generic inference and tool bases in `core`, registrations in `catalog`,
execution in `runner`, and integrations in `adapters`. The public tools package
re-exports the existing core classes so registry and adapter identity is preserved.

This aligns public imports with the target application structure in VISION.md.
Inference split criteria were checked: this changes package ownership and imports,
not domain behavior, so no new domain-specific bases are needed. General choice
execution and framework tools in Codex remain outside this change.

Verification: 282 non-live tests passed, including authoring import boundaries.
A clean package build includes all new public packages and excludes `definitions`.
`git diff --check` passed.
Maintain usage and architecture in README.md and VISION.md. Retirement covers only
this file; preserve it until its exact content is recoverable from Git.
