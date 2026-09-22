"""Execute registered workflow definitions and record their runs."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from django.db import transaction

from agents.core.agent import AgentConfig
from agents.core.json_safe import json_safe
from agents.core.step import Step
from agents.core.workflow import Workflow, WorkflowRegistry
from agents.models import (
    AgentRun,
    AgentRunStatus,
    PipelineRun,
    PipelineStatus,
    PipelineStep,
)
from agents.runner.agent import ManagedAgent

logger = logging.getLogger(__name__)


def create_workflow_run(
    workflow_name: str,
    payload: dict[str, Any],
    *,
    workflow_cls: type[Workflow] | None = None,
) -> str:
    """Create the persisted run accepted by an executor."""

    definition = workflow_cls or WorkflowRegistry.get(workflow_name)
    if definition.name != workflow_name:
        raise ValueError(
            f"Workflow definition '{definition.name}' does not match '{workflow_name}'."
        )
    run = PipelineRun.create_run(
        pipeline_name=workflow_name,
        root_payload=payload,
        context={},
    )
    return str(run.id)


def _resolve_parents(
    run: PipelineRun,
    parent_ids: list[str] | None,
) -> list[PipelineStep]:
    try:
        requested_ids = {UUID(str(parent_id)) for parent_id in parent_ids or []}
    except ValueError as error:
        raise ValueError("Parent IDs must be valid UUIDs") from error

    parents = list(
        PipelineStep.objects.select_for_update().filter(
            run=run,
            pk__in=requested_ids,
        )
    )
    if {parent.id for parent in parents} != requested_ids:
        raise ValueError(f"Parent steps must belong to pipeline run {run.id}")
    return parents


def _unwrap_hook_result(value: Any) -> Any:
    return value[0] if isinstance(value, tuple) else value


def _run_agent_step(
    managed_agent: ManagedAgent,
    agent_run_id: UUID,
    step_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    output = managed_agent.run_sync(
        input_payload=payload,
        agent_label=step_name,
        step_name=step_name,
    )
    agent_run = AgentRun.objects.get(pk=agent_run_id)
    if agent_run.status != AgentRunStatus.SUCCEEDED:
        raise RuntimeError(agent_run.error_message or "Agent run failed")
    return output


def execute_workflow_step(
    *,
    run_id: str,
    workflow_name: str,
    step_key: str,
    payload: dict[str, Any],
    order_index: int,
    parent_ids: list[str] | None = None,
    agent_config: AgentConfig | None = None,
    workflow_cls: type[Workflow] | None = None,
) -> dict[str, Any]:
    """Execute one step from a workflow definition under the managed lifecycle."""

    definition = workflow_cls or WorkflowRegistry.get(workflow_name)
    if definition.name != workflow_name:
        raise ValueError(
            f"Workflow definition '{definition.name}' does not match '{workflow_name}'."
        )
    if step_key not in definition.steps:
        raise ValueError(
            f"Step '{step_key}' not registered in Workflow '{workflow_name}'"
        )

    step: Step = definition.steps[step_key]()
    config = agent_config if agent_config is not None else step.agent_config
    with transaction.atomic():
        run = PipelineRun.objects.get(pk=run_id)
        parents = _resolve_parents(run, parent_ids)
        managed_agent = None
        agent_run = None
        if config is not None:
            managed_agent = ManagedAgent(config=config, agent_label=step_key)
            agent_run = AgentRun.objects.get(pk=managed_agent.run_id)
        step_record = PipelineStep.create_step(
            run=run,
            step_name=step_key,
            order_index=order_index,
            input_payload=payload,
            agent_run=agent_run,
        )
        step_record.parents.set(parents)

    step_record.mark_running()
    run.set_running(step_key)

    try:
        processed_payload = _unwrap_hook_result(step.pre_execute(payload, {}))
        if managed_agent is not None and agent_run is not None:
            output = _run_agent_step(
                managed_agent,
                agent_run.id,
                step_key,
                processed_payload,
            )
        else:
            output = step.execute(processed_payload)
        final_output = json_safe(_unwrap_hook_result(step.post_execute(output, {})))
        step_record.mark_finished(
            PipelineStatus.SUCCEEDED,
            output_payload=final_output,
        )
        return final_output
    except Exception as error:
        logger.exception(
            "Workflow step failed",
            extra={"workflow_name": workflow_name, "step_key": step_key, "run_id": run_id},
        )
        step_record.mark_finished(PipelineStatus.FAILED, error=str(error))
        raise


def mark_workflow_success(run_id: str, workflow_name: str) -> None:
    """Mark a workflow run as successful after validating its definition."""

    WorkflowRegistry.get(workflow_name)
    PipelineRun.objects.get(pk=run_id).mark_succeeded()


def mark_workflow_failure(
    run_id: str,
    workflow_name: str,
    error: str | None = None,
) -> None:
    """Mark a workflow run as failed after validating its definition."""

    WorkflowRegistry.get(workflow_name)
    PipelineRun.objects.get(pk=run_id).mark_failed()


__all__ = (
    "create_workflow_run",
    "execute_workflow_step",
    "mark_workflow_failure",
    "mark_workflow_success",
)
