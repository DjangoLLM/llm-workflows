"""
Step registration and dispatch catalog for pipeline execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type

from agents.core.agent import AgentConfig
from agents.core.agent_config_catalog import AgentConfigCatalog
from agents.core.pipeline_structure import Pipeline, PipelineRegistry, PipelineStep


class StepExecutionType(str, Enum):
    """
    Supported step execution modes.
    """

    LLM = "LLM"
    CODE = "CODE"


@dataclass(frozen=True)
class StepRegistration:
    """
    Immutable step registration metadata.

    :param key: Stable unique key for lookup.
    :param pipeline_name: Owning pipeline name.
    :param step_class: Step class implementation.
    :param execution_type: LLM or CODE execution mode.
    :param default_timeout_seconds: Optional default timeout.
    :param retry_policy: Optional retry metadata for worker wiring.
    :param agent_config_key: Optional AgentConfig resolver key.
    """

    key: str
    pipeline_name: str
    step_class: Type[PipelineStep]
    execution_type: StepExecutionType
    default_timeout_seconds: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    agent_config_key: Optional[str] = None


class StepCatalog:
    """
    Global catalog for step metadata and runtime dispatch.

    Responsibilities:
    - Register and resolve step metadata by key.
    - Validate catalog consistency at startup.
    - Execute registered steps through existing pipeline runtime.
    """

    _steps: Dict[str, StepRegistration] = {}

    @classmethod
    def register_step(
        cls,
        key: str,
        pipeline_name: str,
        step_class: Type[PipelineStep],
        execution_type: StepExecutionType | str,
        default_timeout_seconds: Optional[int] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        agent_config_key: Optional[str] = None,
    ) -> None:
        """
        Register one step metadata record.

        :param key: Stable unique key for this step.
        :param pipeline_name: Owning pipeline name.
        :param step_class: Step class implementation.
        :param execution_type: LLM or CODE step mode.
        :param default_timeout_seconds: Optional runtime timeout.
        :param retry_policy: Optional retry policy metadata.
        :param agent_config_key: Optional AgentConfig key for LLM steps.
        :return: None.
        :raises ValueError: If key is missing or duplicate.
        """
        if not key:
            raise ValueError("Step key cannot be empty.")

        if key in cls._steps:
            raise ValueError(f"Duplicate step key '{key}'.")

        normalized_type = StepExecutionType(execution_type)
        cls._steps[key] = StepRegistration(
            key=key,
            pipeline_name=pipeline_name,
            step_class=step_class,
            execution_type=normalized_type,
            default_timeout_seconds=default_timeout_seconds,
            retry_policy=retry_policy,
            agent_config_key=agent_config_key,
        )

    @classmethod
    def get_step(cls, key: str) -> StepRegistration:
        """
        Resolve step metadata by key.

        :param key: Registered step key.
        :return: StepRegistration metadata.
        :raises ValueError: If key is not registered.
        """
        if key not in cls._steps:
            raise ValueError(f"Unknown step key '{key}'.")
        return cls._steps[key]

    @classmethod
    def list_step_keys(cls) -> list[str]:
        """
        Return all registered step keys.

        :return: Sorted list of keys.
        """
        return sorted(cls._steps.keys())

    @classmethod
    def validate_registry(cls) -> None:
        """
        Validate all registered step metadata.

        :return: None.
        :raises TypeError: If step contracts are invalid.
        :raises ValueError: If pipeline/step wiring is inconsistent.
        """
        for key in cls.list_step_keys():
            metadata = cls._steps[key]

            if not issubclass(metadata.step_class, PipelineStep):
                raise TypeError(f"Step '{key}' must inherit PipelineStep.")

            pipeline_cls = PipelineRegistry.get(metadata.pipeline_name)
            cls._validate_pipeline_mapping(key, metadata, pipeline_cls)
            cls._validate_llm_contract(key, metadata)

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
        pipeline_instance = pipeline_cls(payload=payload, run_id=run_id)
        resolved_config = cls._resolve_optional_agent_config(metadata)
        return pipeline_instance.execute_step(
            run_id=run_id,
            step_key=step_key,
            payload=payload,
            order_index=order_index,
            parent_ids=parent_ids,
            agent_config=resolved_config,
        )

    @classmethod
    def _resolve_optional_agent_config(
        cls,
        metadata: StepRegistration,
    ) -> Optional[AgentConfig]:
        """
        Resolve configured AgentConfig for LLM metadata.

        :param metadata: Step registration metadata.
        :return: AgentConfig if configured, otherwise None.
        """
        if metadata.execution_type != StepExecutionType.LLM:
            return None
        if not metadata.agent_config_key:
            return None
        return AgentConfigCatalog.resolve_agent_config(metadata.agent_config_key)

    @classmethod
    def _validate_pipeline_mapping(
        cls,
        key: str,
        metadata: StepRegistration,
        pipeline_cls: Type[Pipeline],
    ) -> None:
        """
        Validate step key and class mapping on pipeline.

        :param key: Step key being validated.
        :param metadata: Step registration metadata.
        :param pipeline_cls: Pipeline class resolved from registry.
        :return: None.
        :raises ValueError: If step key/class does not match pipeline.
        """
        if key not in pipeline_cls.steps:
            raise ValueError(
                f"Step '{key}' missing from pipeline '{metadata.pipeline_name}' steps map."
            )

        pipeline_step_class = pipeline_cls.steps[key]
        if pipeline_step_class is not metadata.step_class:
            raise ValueError(
                f"Step class mismatch for '{key}' in pipeline '{metadata.pipeline_name}'."
            )

    @classmethod
    def _validate_llm_contract(cls, key: str, metadata: StepRegistration) -> None:
        """
        Validate LLM-specific registration requirements.

        :param key: Step key being validated.
        :param metadata: Step registration metadata.
        :return: None.
        :raises ValueError: If LLM registration is invalid.
        """
        if metadata.execution_type != StepExecutionType.LLM:
            return

        # Validate optional cross-reference to config catalog.

        if metadata.agent_config_key:
            AgentConfigCatalog.resolve_agent_config(metadata.agent_config_key)
            return

        # Validate class-level fallback contract.

        agent_config_attr = getattr(metadata.step_class, "agent_config", None)
        if (
            not isinstance(agent_config_attr, property)
            or agent_config_attr is PipelineStep.agent_config
        ):
            raise ValueError(
                f"LLM step '{key}' requires agent_config_key or agent_config property."
            )
