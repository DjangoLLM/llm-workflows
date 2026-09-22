# Shared inference bases with separate adapter contracts

Status: retirement pending. Implementation and verification complete.

## Decision and scope

Keep Definition, DefinitionCatalog[T], InferenceAdapter[ResultT], and
InferenceRunner[ResultT] in core/inference/. Keep only AgentAdapter and
ChoiceAdapter specialized, under core/inference/adapters/agent.py and choice.py.
Remove intermediate domain definition, catalog, and runner bases.

Public AgentDefinition and ChoiceDefinition inherit Definition directly and own
their fields and validation. Concrete catalogs inherit DefinitionCatalog directly
and own independent registry storage. Public imports remain unchanged.

Agent extends InferenceRunner and selects Codex. JevIf wraps its Jev adapter in
the same InferenceRunner. Persistence remains in ManagedAgent. Core imports only
core and the standard library. General ChoiceDefinition execution and
ManagedChoice are outside this change.

## Verification

Verified with 279 non-live unit, integration, and demo tests, including catalog
isolation, shared runner delegation and error propagation for both adapters,
managed Jev success/failure, and runtime-free core imports. A clean package
build includes the shared bases and adapters package and excludes the removed
domain packages. README.md and spec/VISION.md describe the final organization.

## Retirement

Retirement path: spec/inference-domain-split.md, with no HTML or owned assets.
The file is untracked and must remain until its exact content is recoverable
from Git. Do not create a commit only to permit retirement.
