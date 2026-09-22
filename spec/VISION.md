# Project vision: build, operate, evaluate, and improve workflows

Freedom Agents is a workflow-building harness. It provides the conventions, code, and execution primitives an agent needs to turn a user's task into a saved, reusable workflow expressed as code. The product name remains provisional.

The product's scope extends through the workflow's life: build, operate, evaluate, and improve. Building a reusable workflow is the starting point. Users must also be able to understand its executions, assess the quality of its results, and use that evidence to improve subsequent versions.

The larger goal is to let a user collaborate with an agent to perform a task, capture the procedure, and produce a workflow they can run repeatedly with different inputs. Workflows combine ordinary code with Jev or LLM calls where judgment is required. Browser interaction is the initial authoring scope; the shared workflow model must support other capabilities later.

Execution must be durable, with explicit decisions, recoverable steps, and a history that explains how each run reached its outcome. A failure during decision-making or branch execution should not force the entire run to start over or lose completed work.

This document records the agreed product direction and target contracts. It is not an implementation specification or a claim that every capability below exists today. Canonical terms live in [the domain glossary](../CONTEXT.md).

## Intended user experience

1. The user describes a task and performs it collaboratively with an agent in a browser. The collaboration establishes the intended outcome, relevant inputs, decision criteria, and points requiring human review.
2. The agent captures the procedure in a detailed, reviewable definition, initially envisioned as Markdown. It describes inputs, outputs, steps, decisions, and failure handling.
3. The harness turns that definition into workflow code following a prescribed authoring contract, validates the result, and saves it for reuse. The procedure and executable must remain consistent when revised.
4. Suitable LLM decisions can be replaced with Jev evaluation while preserving their contracts. Mechanical operations use ordinary code. A lack of generated prose alone does not establish that an operation fits Jev.
5. The user runs the saved workflow repeatedly with new inputs and inspects each run's decisions, outputs, and artifacts.

The builder must provide instructions, APIs, and validation tools that make this authoring contract usable by an agent. The executor supplies the runtime and execution history. A reusable workflow is the output of the building process.

## Target application structure and authoring process

A coding agent builds reusable workflows by finding existing capabilities and
creating missing ones. It authors task-specific agents with explicit instructions,
permitted tools, and expected results, and choices with declared candidates and
selection criteria.

Applications built with this library should organize their authored code around
these responsibilities:

```text
inferences/
  agents/
  choices/
tools/
steps/
workflows/
```

| Application folder | Responsibility |
| --- | --- |
| `inferences/agents/` | Task-specific agent definitions, including instructions, permitted tools, and result contracts. |
| `inferences/choices/` | Bounded decision definitions, including classification and selections that workflows may use for routing. |
| `tools/` | Reusable operations and toolsets that group related tools. |
| `steps/` | Units of workflow work with input/output contracts, implemented through ordinary code, an agent, or a choice. |
| `workflows/` | Composition of steps, data flow, sequencing, branching, iteration, and recovery. |

A choice returns a decision. The workflow owns branching on that decision.
Classification can be a choice step whose output is passed to later steps as data
without changing the execution path. For example, a feedback workflow can fetch
feedback with a tool, classify it with a choice, branch on the category, invoke a
specialized agent to investigate a bug, and save the result with a tool.

The coding agent's workflow-building process is:

1. Establish the workflow's inputs, expected outputs, and required operations.
2. Discover reusable tools, agent definitions, choices, and steps through the
   available catalogs and authoring interfaces.
3. Create the missing capabilities, with explicit contracts and permitted tools.
4. Wire those capabilities into steps and compose the steps into a workflow.
5. Validate input/output compatibility and test execution, decisions, and routing.

This is the target application layout. The library provides its supporting
machinery through `core`, `catalog`, `runner`, and `adapters`. Its public interfaces
mirror the application concepts through `inferences`, `tools`, `steps`, and
`workflows`.
Application authors should primarily work with their task definitions and
composition; they should not need to reproduce the library's internal layout.

Use this authoring process to guide future public interfaces, catalog discovery,
examples, and implementation decisions. Keep reusable capabilities independently
discoverable and composable. Preserve the separation between task definitions,
execution records, and provider integrations as the library evolves.

This direction does not establish that all authoring capabilities are implemented.
General choice execution and `ManagedChoice` remain future work, and the current
Codex integration rejects `AgentDefinition.tools` and `toolsets`; connecting those
permitted tool definitions to agent execution is still an implementation gap.

## Operating, evaluating, and improving workflows

The product should provide a UI for inspecting workflow execution history, with the operational ergonomics the user associates with Airflow. Users should be able to see what ran, what happened within a run, and how it reached its outcome. The detailed UI and its operational controls remain to be designed.

Evals should assess the quality of agent and workflow results. Successful execution alone does not establish that the result was good. Evaluation should help compare changes and identify regressions.

Self-improvement loops should connect execution evidence and feedback to proposed changes and evaluation of those changes. The scope of changes, promotion criteria, and degree of autonomy remain open design decisions.

Agent ergonomics are also part of the product direction. The balance between helping agents author and debug workflows and helping agents during execution remains to be clarified.

These are agreed growth directions, not an implementation sequence or a claim that the capabilities already exist.

## Core primitives

| Primitive | Target responsibility |
| --- | --- |
| `AgentDefinition` | Define instructions, model/backend, reasoning settings, permitted tools, and the agent's input/output contract. |
| `ManagedAgent` | Execute an agent and record inputs, outputs, available execution trace, status, and errors. |
| `ChoiceDefinition` | Define a decision question, selection criteria, typed input, allowed options, typed output, selection cardinality, and evaluator configuration. |
| `ManagedChoice` | Evaluate a choice, validate its result, and record the input, actual candidates, decision, available trace, status, and errors. |
| `Step` | Represent a unit of workflow work with an input/output contract, implemented by code, an agent, or a choice. |
| `Workflow` | Compose steps in code, owning data flow, branching, iteration, concurrency, and recovery. |

A run is a particular execution of a definition. Repeated workflow runs and repeated step executions need distinct identities. Workflows that compare observations over time also need explicit persistent state between runs; that state is separate from the inputs and outputs of an individual run.

## Choice contract

Choice is a first-class authoring concept for bounded judgment. Prefer it wherever the decision can be expressed as selection among declared alternatives. Use general agent steps for work that requires producing results beyond those alternatives.

`ChoiceDefinition` and `ManagedChoice` mirror the definition/execution separation of `AgentDefinition` and `ManagedAgent`:

- Inputs have a declared schema and supply the context needed to decide.
- Options may be fixed in the definition or supplied at invocation time. For dynamic options, the definition declares the option schema and each execution records the actual candidate set.
- Outputs have a declared schema and encode selections structurally using candidate identifiers. Downstream code must not have to interpret prose to discover the decision.
- The contract declares single or multiple selection and whether an explicit `no_match` outcome is allowed.
- Validation checks both the output schema and membership in the supplied candidate set, along with selection cardinality.
- A valid `no_match` decision is distinct from an execution failure or invalid result. The workflow declares how to handle each relevant outcome.

`ManagedChoice` returns a validated decision. The workflow determines what to execute next. Selecting a project can supply data to a later step without requiring a separate branch for every project.

The contract should permit Jev, an LLM, or code to supply the decision. Replacing the evaluator must preserve the contract and be validated against representative cases; matching types alone does not establish equivalent decision quality.

Choice can be implemented as a specialized step and can share execution and persistence machinery with managed agents. Whether `ManagedChoice` delegates internally to `ManagedAgent` is an implementation decision still to be made.

## Examples that test the model

The X example is an illustrative workflow, not the product's scope: gather relationship information in the browser, compare accounts and available history, and produce an Excel review sheet containing profile links. The user reviews the sheet and decides whom to unfollow. Current lists establish who does not follow back; proving someone later unfollowed requires historical evidence, and proving the user originally followed them back requires the corresponding relationship history. The workflow may need a baseline and persistent snapshots between runs.

The recording/MEML example illustrates different kinds of work, without prescribing its exact production sequence:

- Assessing how many topics exist produces data.
- Splitting the recording produces a collection through an agent transformation.
- Processing each slice uses workflow iteration.
- Selecting the relevant project/module is a choice with candidates supplied from available projects/modules.
- Classifying a slice can select a subsequent processing path.

Not every uncertain result is a branch. Choice produces a bounded decision; workflow code consumes it as data or control flow.

## Execution model

A choice becomes a recorded input to execution:

1. `ManagedChoice` evaluates the current state using its configured evaluator.
2. It validates and records the structured selection against the choice contract and supplied candidates.
3. The workflow executes the selected branch.
4. If the branch fails, an explicit recovery policy determines whether to retry it, evaluate a new choice, or wait for help.

The evaluator supplies judgment. The workflow owns execution order, routing the validated decision, and recovery policy. Decision result types must match the payloads expected by workflow activities.

## Recovery principles

Retrying work preserves the existing decision. Asking the evaluator to choose again is a separate execution with its own recorded inputs and result. Recovery should not silently change what the run was trying to do.

The recovery boundary must be explicit. A single inference call and a long agent conversation containing several tool actions require different recovery handling. Each workflow should define which completed work it preserves and which work it may repeat after a failure.

Actions that change external systems need protection against duplicate execution. Durable execution alone does not make those actions safe to repeat.

Durability preserves progress and supports recovery; it does not guarantee that every failure can be resolved automatically. Workflows need explicit policies for exhausted retries, invalid choices, and situations requiring human input.

## Fit with the existing codebase

The installable library lives in `src/`; its import name remains `agents`.
Library folder paths in this document are relative to that directory. Tests,
examples, documentation, and specs remain outside the installable package.

The package separates generic bases, public definitions, catalogs, execution, and adapters:

- `agents.core.inference` contains shared definition, catalog, adapter, and runner bases.
- `agents.core.tools` contains shared tool contracts, the `ToolSet` base, and the
  `tool` decorator. Tool schemas use Pydantic; these contracts do not import execution integrations.
- `agents.inferences.agents` and `agents.inferences.choices` expose agent and choice definitions.
- `agents.tools` exposes the shared tool authoring contracts from `core/tools`.
- `agents.steps` and `agents.workflows` expose step and workflow definitions.
- `agents.catalog` stores registered definitions.
- `agents.runner` accepts those registered definitions and owns execution and
  persistence. Tool registration and lookup live in `agents.catalog.tool_catalog`;
  `agents.runner.tools` retains compatibility imports.
- `agents.adapters.inference` contains Codex and Jev integrations.
- `agents.adapters.tools` contains tool model conversion and MCP integration.
- `agents.adapters.temporal` contains workflow orchestration integration.

Target applications depend on the definition interface. Executor setup depends
on the runner interface. The persisted `PipelineRun` and `PipelineStep` model
names remain for database compatibility; they do not define the public
authoring vocabulary.

`AgentDefinition` already includes instructions, model/backend configuration, tools, and `result_type`. Its current Python definition does not declare a corresponding input schema. The inspected `ManagedAgent` persistence path records inputs, outputs, status, and errors, but does not persist the intermediate execution trace. Typed input contracts and trace persistence above are target responsibilities.

`ChoiceDefinition` is now a definition-only contract in `agents.inferences.choices`. General
choice evaluation, result validation, and `ManagedChoice` remain unimplemented.

## Inference architecture and split criteria

Reusable inference contracts live in `core/inference/`. Shared `Definition`,
`DefinitionCatalog[T]`, `InferenceAdapter[ResultT]`, and `InferenceRunner[ResultT]`
bases live in the parent package. Separate `AgentAdapter` and `ChoiceAdapter`
contracts live in `core/inference/adapters/agent.py` and `choice.py`.
Concrete agent and choice definitions live in `inferences/`, concrete catalogs in
`catalog/`, and provider integrations in `adapters/`.

Both public definitions inherit `Definition` directly and own their respective
fields and validation. Both concrete catalogs inherit `DefinitionCatalog[T]`
directly. There are no intermediate domain definition, catalog, or runner bases.

The public `Agent` and the Jev choice path use shared synchronous and asynchronous
adapter delegation from `InferenceRunner`. Codex implements `AgentAdapter`;
Jev implements `ChoiceAdapter`. The core bases do not import runtime integrations
or perform persistence. General choice execution remains future work.

`AgentDefinitionCatalog` and `ChoiceDefinitionCatalog` inherit common factory
registration, key lookup, result-type validation, and sorted-key behavior from
`DefinitionCatalog[T]`. Each concrete catalog owns independent storage. Keep
this shared implementation while those operations have the same semantics.
Registering the same key in both catalogs must remain valid; registering or
clearing entries in one must leave the other unchanged.

Agent and choice behavior differs beyond registration. Agents produce results
matching an output schema. Choices select from declared candidates and enforce
candidate membership, selection cardinality, and any permitted `no_match`
outcome. Their common `run` and `run_sync` methods alone do not establish that
their complete execution contracts are interchangeable.

Review the following criteria whenever adding an evaluator or provider,
implementing managed choice execution, or changing definition, catalog, or
adapter contracts:

| Evidence in the proposed change | Architectural response |
| --- | --- |
| The common adapter needs agent/choice type checks, domain-specific optional arguments, or methods that one kind cannot support. | Extend the existing domain-specific adapter contracts. Keep only behavior both can meaningfully implement in the shared base. |
| Choice execution needs explicit candidate inputs and validated selections, while agent execution requires a different input/output contract. | Define typed agent and choice adapter contracts before extending the generic interface with loosely typed payloads or flags. |
| Catalog registration, lookup, or lifecycle rules diverge, requiring domain switches or overrides that bypass shared validation. | Separate the differing catalog policies. Share only the remaining common mechanics; preserve independent registry storage. |
| Distinct agent and choice contracts develop their own validation or lifecycle rules. | Keep domain rules in the concrete definitions and specialized adapter contracts. Reconsider domain-specific definition or runner bases only when multiple implementations need the same domain behavior. |

A new provider or additional domain-specific adapter behavior does not by
itself justify separate catalog base classes. Keep one generic catalog until
its registration or lookup semantics need to differ.

When a criterion is met, record the concrete evidence and selected response in
the active implementation spec before expanding the shared abstraction. List
that work in `spec/README.md`. Include import migration and tests for the new
contracts, result validation, and catalog isolation. If the split is deferred,
record why and what future change will trigger reconsideration. These are
review checkpoints; no automated architecture detector currently exists.

## Scope of the shared foundation

The shared package should provide the authoring, execution, and recovery capabilities that multiple applications need. Individual applications supply their domain-specific steps, candidates, available paths, agent instructions, and recovery policies.

This document records the project direction. It does not claim that all of these recovery guarantees or decision contracts are already implemented.
