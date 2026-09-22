"""
Step definitions, registration metadata, and structural validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type

from agents.steps import Step
from agents.workflows import Workflow
from agents.catalog.workflow_catalog import WorkflowRegistry


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
    :param agent_definition_key: Optional AgentDefinition resolver key.
    """

    key: str
    pipeline_name: str
    step_class: Type[Step]
    execution_type: StepExecutionType
    default_timeout_seconds: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    agent_definition_key: Optional[str] = None


class StepCatalog:
    """
    Catalog of registered step definitions.

    Responsibilities:
    - Register and resolve step metadata by key.
    - Validate catalog consistency at startup.
    """

    _steps: Dict[str, StepRegistration] = {}

    @classmethod
    def register_step(
        cls,
        key: str,
        pipeline_name: str,
        step_class: Type[Step],
        execution_type: StepExecutionType | str,
        default_timeout_seconds: Optional[int] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        agent_definition_key: Optional[str] = None,
    ) -> None:
        """
        Register one step metadata record.

        :param key: Stable unique key for this step.
        :param pipeline_name: Owning pipeline name.
        :param step_class: Step class implementation.
        :param execution_type: LLM or CODE step mode.
        :param default_timeout_seconds: Optional runtime timeout.
        :param retry_policy: Optional retry policy metadata.
        :param agent_definition_key: Optional AgentDefinition key for LLM steps.
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
            agent_definition_key=agent_definition_key,
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

            if not issubclass(metadata.step_class, Step):
                raise TypeError(f"Step '{key}' must inherit Step.")

            pipeline_cls = WorkflowRegistry.get(metadata.pipeline_name)
            cls._validate_pipeline_mapping(key, metadata, pipeline_cls)
            cls._validate_llm_contract(key, metadata)

    @classmethod
    def _validate_pipeline_mapping(
        cls,
        key: str,
        metadata: StepRegistration,
        pipeline_cls: Type[Workflow],
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

        # Validate optional cross-reference to definition catalog.

        if metadata.agent_definition_key:
            return

        # Validate class-level fallback contract.

        agent_definition_attr = getattr(metadata.step_class, "agent_definition", None)
        if (
            not isinstance(agent_definition_attr, property)
            or agent_definition_attr is Step.agent_definition
        ):
            raise ValueError(
                f"LLM step '{key}' requires agent_definition_key or agent_definition property."
            )


def register_step(
    *,
    key: str,
    workflow_name: str,
    step_class: Type[Step],
    execution_type: StepExecutionType | str,
    default_timeout_seconds: Optional[int] = None,
    retry_policy: Optional[Dict[str, Any]] = None,
    agent_definition_key: Optional[str] = None,
) -> None:
    """Register a step definition with the default catalog."""

    StepCatalog.register_step(
        key=key,
        pipeline_name=workflow_name,
        step_class=step_class,
        execution_type=execution_type,
        default_timeout_seconds=default_timeout_seconds,
        retry_policy=retry_policy,
        agent_definition_key=agent_definition_key,
    )
