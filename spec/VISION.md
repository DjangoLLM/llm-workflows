# Project vision: durable execution for Jev-directed work

This project is the reusable execution foundation for the Jev applications we plan to build. It runs AI pipelines that combine ordinary code with non-deterministic decisions. At some points, a Jev evaluates the current state and decides which path to take.

The purpose is to run Jev-directed work durably, with explicit decisions, recoverable steps, and a history that explains how each run reached its outcome. A failure during decision-making or branch execution should not force the entire run to start over or lose completed work.

## Execution model

A Jev's decision becomes a recorded input to execution:

1. The Jev evaluates the current state and returns a structured choice.
2. The workflow validates that choice against the allowed paths.
3. The workflow executes the selected branch.
4. If the branch fails, an explicit recovery policy determines whether to retry it, ask the Jev to reconsider, or wait for help.

The Jev supplies judgment. The workflow owns execution order, branch validation, and recovery policy. Decisions should have explicit result types or output schemas that match the payloads expected by workflow activities.

## Recovery principles

Retrying work preserves the existing decision. Asking the Jev to choose again is a separate step with its own recorded inputs and result. Recovery should not silently change what the run was trying to do.

The recovery boundary must be explicit. A single inference call and a long agent conversation containing several tool actions require different recovery handling. Each workflow should define which completed work it preserves and which work it may repeat after a failure.

Actions that change external systems need protection against duplicate execution. Durable execution alone does not make those actions safe to repeat.

Durability preserves progress and supports recovery; it does not guarantee that every failure can be resolved automatically. Workflows need explicit policies for exhausted retries, invalid choices, and situations requiring human input.

## Fit with the existing codebase

The current separation of responsibilities supports this direction:

- `Pipeline` groups execution records and tracks the run lifecycle.
- `PipelineStep` records a unit of execution and its inputs and outputs.
- `ManagedAgent` runs AI work and tracks its state.
- Temporal workflows own ordering, branching, retries, and failure handling.

The MCP loop example already demonstrates an agent choosing tools inside a workflow. That is an example of the broader Jev-directed execution model, rather than the complete definition of it.

## Scope of the shared foundation

The shared package should provide the execution and recovery capabilities that multiple Jev applications need. Individual applications supply their domain-specific steps, available paths, agent instructions, and recovery policies.

This document records the project direction. It does not claim that all of these recovery guarantees or decision contracts are already implemented.
