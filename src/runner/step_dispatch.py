"""Runtime dispatch and definition resolution for registered steps."""
from typing import Optional
from agents.inferences.agents import AgentDefinition
from agents.catalog.step_catalog import StepCatalog, StepRegistration, StepExecutionType
from agents.workflows import Workflow
from agents.runner.pipeline_structure import Pipeline, PipelineRegistry
from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog

class StepDispatcher(StepCatalog):
    @classmethod
    def execute_step(
        cls,
        run_id: str,
        pipeline_name: str,
        step_key: str,
        order_index: int,
        payload: dict,
        parent_ids: Optional[list[str]] = None,
    ) -> dict:
        """
        Execute a registered step through existing runtime behavior.

        :param run_id: Existing PipelineRun UUID.
        :param pipeline_name: Owning pipeline name.
        :param step_key: Step key to execute.
        :param order_index: Observational step order index.
        :param payload: Step input payload.
        :param parent_ids: Optional parent lineage ids.
        :return: Step output payload.
        :raises ValueError: If pipeline/step ownership mismatches.
        """
        metadata = cls.get_step(step_key)
        if metadata.pipeline_name != pipeline_name:
            raise ValueError(
                f"Step '{step_key}' belongs to '{metadata.pipeline_name}', not '{pipeline_name}'."
            )

        pipeline_cls = PipelineRegistry.get(pipeline_name)
        resolved_definition = cls._resolve_optional_agent_definition(metadata)
        if issubclass(pipeline_cls, Workflow) and not issubclass(
            pipeline_cls, Pipeline
        ):
            from agents.runner.workflow import execute_workflow_step

            return execute_workflow_step(
                run_id=run_id,
                workflow_name=pipeline_name,
                step_key=step_key,
                payload=payload,
                order_index=order_index,
                parent_ids=parent_ids,
                agent_definition=resolved_definition,
                workflow_cls=pipeline_cls,
            )

        pipeline_instance = pipeline_cls(payload=payload, run_id=run_id)
        return pipeline_instance.execute_step(
            run_id=run_id,
            step_key=step_key,
            payload=payload,
            order_index=order_index,
            parent_ids=parent_ids,
            agent_definition=resolved_definition,
        )

    @classmethod
    def _resolve_optional_agent_definition(
        cls,
        metadata: StepRegistration,
    ) -> Optional[AgentDefinition]:
        """
        Resolve configured AgentDefinition for LLM metadata.

        :param metadata: Step registration metadata.
        :return: AgentDefinition if configured, otherwise None.
        """
        if metadata.execution_type != StepExecutionType.LLM:
            return None
        if not metadata.agent_definition_key:
            return None
        return AgentDefinitionCatalog.resolve_agent_definition(metadata.agent_definition_key)

    @classmethod
    def resolve_agent_definition(
        cls,
        metadata: StepRegistration,
    ) -> Optional[AgentDefinition]:
        """Resolve the agent definition attached to a registration."""

        return cls._resolve_optional_agent_definition(metadata)
