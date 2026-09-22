"""Compatibility names for the former pipeline authoring API."""

from __future__ import annotations

from typing import Any

from agents.steps import Step
from agents.workflows import Workflow
from agents.catalog.workflow_catalog import WorkflowRegistry


PipelineStep = Step
PipelineRegistry = WorkflowRegistry


class Pipeline(Workflow):
    """Deprecated workflow name with legacy convenience methods."""

    def __init__(self, payload: dict[str, Any], run_id: str | None = None):
        self.payload = payload
        if run_id is None:
            from agents.runner.workflow import create_workflow_run

            run_id = create_workflow_run(
                self.name,
                payload,
                workflow_cls=type(self),
            )
        self.run_id = run_id

    @classmethod
    def create_run(cls, payload: dict[str, Any]) -> str:
        from agents.runner.workflow import create_workflow_run

        return create_workflow_run(cls.name, payload, workflow_cls=cls)

    def execute_step(
        self,
        run_id: str | None,
        step_key: str,
        payload: dict[str, Any],
        order_index: int,
        parent_ids: list[str] | None = None,
        agent_definition=None,
    ) -> dict[str, Any]:
        from agents.runner.workflow import execute_workflow_step

        effective_run_id = run_id or self.run_id
        if effective_run_id is None:
            raise ValueError("run_id is required to execute a step")
        if step_key not in self.steps:
            raise ValueError(
                f"Step '{step_key}' not registered in Pipeline '{self.name}'"
            )
        return execute_workflow_step(
            run_id=effective_run_id,
            workflow_name=self.name,
            step_key=step_key,
            payload=payload,
            order_index=order_index,
            parent_ids=parent_ids,
            agent_definition=agent_definition,
            workflow_cls=type(self),
        )

    @classmethod
    def mark_success(cls, run_id: str) -> None:
        from agents.runner.workflow import mark_workflow_success

        mark_workflow_success(run_id, cls.name)

    @classmethod
    def mark_failure(cls, run_id: str, error: str | None = None) -> None:
        from agents.runner.workflow import mark_workflow_failure

        mark_workflow_failure(run_id, cls.name, error)


__all__ = ("Pipeline", "PipelineRegistry", "PipelineStep")
