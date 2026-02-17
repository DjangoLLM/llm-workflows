import logging
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Type, Any, Optional

from agents.agent import Agent, AgentConfig, ManagedAgent
from agents.models import PipelineRun, PipelineStep as PipelineStepModel, PipelineStatus, AgentRun, AgentRunStatus

logger = logging.getLogger(__name__)


class PipelineStep(ABC):
    """
    Ledger-aware unit of pipeline execution.

    Each PipelineStep records what happened for one step execution:
    - Belongs to a specific PipelineRun parent
    - Optionally uses a ManagedAgent for AI-driven processing
    - Tracks execution state via a PipelineStepModel database record
    - Supports payload and output shaping hooks
    - Stores optional lineage references to earlier steps
    """

    def __init__(
        self,
        run_id: str,
        name: str,
        payload: dict,
        order_index: int,
        parent_ids: Optional[list[str]] = None,
        agent_config: Optional[AgentConfig] = None,
    ):
        """
        Initialize a pipeline step instance.
        
        :param run_id: UUID of the parent PipelineRun
        :param name: Human-readable identifier for this step
        :param payload: Input data dictionary for step execution
        :param order_index: Caller-supplied observational step position
        :param parent_ids: Optional lineage metadata for prior step IDs
        :param agent_config: Optional resolved AgentConfig override
        """
        self.run_id = run_id
        self.name = name
        self.payload = payload
        self.order_index = order_index
        self.parent_ids = parent_ids or []
        self._agent_config_override = agent_config

        # Create database record eagerly with all required data
        run = PipelineRun.objects.get(pk=self.run_id)

        # Initialize agent if configuration provided by subclass
        config = self._resolve_agent_config()
        if config:
            # create Managed Agent for the step
            self._managed_agent = ManagedAgent(config=config, agent_label=self.name)
            self._agent_run_id = self._managed_agent.run_id
            self._agent_run = AgentRun.objects.get(pk=self._agent_run_id)

        else:
            self._managed_agent = None
            self._agent_run = None

        # create the PipelineStep object egarly
        step_model = PipelineStepModel.create_step(
            run=run,
            step_name=self.name,
            order_index=self.order_index,
            input_payload=self.payload,
            agent_run=self._agent_run,
        )

        self._step_model_id = str(step_model.id)

    @property
    def agent_config(self) -> Optional[AgentConfig]:
        """
        Return AgentConfig for this step.

        Subclasses can override this property to provide
        runtime-specific configuration for LLM-backed steps.

        :return: AgentConfig instance or None.
        """
        return None

    def _resolve_agent_config(self) -> Optional[AgentConfig]:
        """
        Resolve effective AgentConfig for this step.

        :return: Override config when provided, else property value.
        """
        if self._agent_config_override is not None:
            return self._agent_config_override
        return self.agent_config

    def pre_execute(
        self,
        payload: dict,
        context: Optional[dict] = None,
    ) -> Tuple[dict, dict] | dict:
        """
        Transform payload before main execution logic runs.

        This hook is payload-focused for ledger-first execution behavior.
        The optional context argument is compatibility-only for legacy steps.

        :param payload: Input data for the step
        :param context: Optional legacy argument for old step signatures
        :return: Transformed payload or legacy (payload, context) tuple
        """
        return payload, context or {}

    def post_execute(
        self,
        result: dict,
        context: Optional[dict] = None,
    ) -> Tuple[dict, dict] | dict:
        """
        Transform output after main execution completes.

        This hook is output-focused for ledger-first execution behavior.
        The optional context argument is compatibility-only for legacy steps.

        :param result: Output data from step execution
        :param context: Optional legacy argument for old step signatures
        :return: Transformed output or legacy (result, context) tuple
        """
        return result, context or {}

    def execute(self, payload: dict) -> dict:
        """
        Core execution logic for the step.
        
        Default implementation delegates to ManagedAgent if configured.
        Subclasses without an agent MUST override this method.
        
        :param payload: Input data for execution
        :return: Output data from step processing
        :raises NotImplementedError: If no agent and not overridden
        """
        if self._managed_agent:
            return self._execute_agent(payload)
        raise NotImplementedError("Steps without an agent must override execute(payload)")

    def _execute_agent(self, payload: dict) -> dict:
        """
        Run the ManagedAgent with input payload.
        
        Executes AI agent synchronously and validates successful completion.
        Retrieves agent run status to verify execution succeeded.
        
        :param payload: Input data for agent processing
        :return: Agent output data
        :raises RuntimeError: If execution failed
        """
        # Run agent synchronously with payload
        output_data = self._managed_agent.run_sync(
            input_payload=payload,
            agent_label=self.name,
            step_name=self.name,
        )

        # Verify agent execution succeeded
        agent_run = AgentRun.objects.get(pk=self._agent_run_id)
        if agent_run.status != AgentRunStatus.SUCCEEDED:
            raise RuntimeError(agent_run.error_message or "Agent run failed")

        return output_data

    def _finalize_success(
        self,
        step_model: PipelineStepModel,
        output_data: dict,
    ) -> dict:
        """
        Complete successful step execution.

        Runs post-execute hook and marks step as succeeded.
        Returns the final transformed output payload.

        :param step_model: PipelineStepModel to mark as succeeded
        :param output_data: Raw output from execute()
        :return: Final transformed output payload
        """
        post_processed = self.post_execute(output_data, {})
        if isinstance(post_processed, tuple):
            final_payload, _ = post_processed
        else:
            final_payload = post_processed

        step_model.mark_finished(PipelineStatus.SUCCEEDED, output_payload=final_payload)
        return final_payload

    def _finalize_failure(self, step_model: PipelineStepModel, error: Exception) -> None:
        """
        Handle step execution failure.
        
        Logs exception details and marks step as failed in database.
        
        :param step_model: PipelineStepModel to mark as failed
        :param error: Exception that caused failure
        """
        logger.exception(f"Step {self.name} in run {self.run_id} failed")
        step_model.mark_finished(PipelineStatus.FAILED, error=str(error))

    def run(self) -> dict:
        """
        Execute the full step lifecycle.

        Standard execution flow:
        1. Load parent run
        2. Run pre_execute() payload shaping
        3. Mark step as running
        4. Execute core logic (agent or custom)
        5. Run post_execute() output shaping
        6. Mark step as succeeded/failed

        :return: Final output payload after post-processing
        :raises Exception: Re-raises any execution errors after marking failed
        """
        # Load parent run
        run = PipelineRun.objects.get(pk=self.run_id)

        # Apply pre-execution payload shaping
        pre_processed = self.pre_execute(self.payload, {})
        if isinstance(pre_processed, tuple):
            processed_payload, _ = pre_processed
        else:
            processed_payload = pre_processed

        # Mark step and run as executing
        step_model = PipelineStepModel.objects.get(pk=self._step_model_id)
        step_model.mark_running()
        run.set_running(self.name)

        try:
            # Execute core step logic
            output_data = self.execute(processed_payload)

            # Finalize success with post-processing
            return self._finalize_success(step_model, output_data)

        except Exception as e:
            # Mark failure and propagate exception
            self._finalize_failure(step_model, e)
            raise


class Pipeline(ABC):
    """
    Ledger-focused wrapper for a specific workflow.

    Each Pipeline subclass defines:
    - A unique workflow name
    - A compatibility map of allowed PipelineStep classes
    - Ledger-focused factory methods for step bookkeeping
    - Methods to manage PipelineRun lifecycle records
    - No orchestration logic; callers control ordering and branching
    """

    name: str = ""
    steps: Dict[str, Type[PipelineStep]] = {}

    def __init__(self, payload: dict, run_id: Optional[str] = None):
        """
        Initialize pipeline instance.
        
        Creates new PipelineRun if no run_id provided, otherwise
        associates with existing run for resumption.
        
        :param payload: Initial workflow input data
        :param run_id: Existing run UUID or None for new run
        """
        self.payload = payload
        self.run_id = run_id

        # Create new run if not resuming existing one

        if self.run_id is None:
            run = PipelineRun.create_run(
                pipeline_name=self.name,
                root_payload=payload,
                context={},
            )
            self.run_id = str(run.id)

    @classmethod
    def create_run(cls, payload: dict) -> str:
        """
        Ledger lifecycle helper to create a PipelineRun.

        This method persists run metadata only.
        Orchestration remains owned by workflow/activity callers.

        TODO: Keep signature stable until registry migration completes.

        :param payload: Initial workflow input data
        :return: UUID string of created PipelineRun
        """
        run = PipelineRun.create_run(
            pipeline_name=cls.name,
            root_payload=payload,
            context={},
        )
        return str(run.id)

    def execute_step(
        self,
        run_id: Optional[str],
        step_key: str,
        payload: dict,
        order_index: int,
        parent_ids: list[str] | None = None,
        agent_config: Optional[AgentConfig] = None,
    ) -> dict:
        """
        Compatibility bridge to instantiate and execute a registered step.

        Resolves a step class from the compatibility map, creates an
        instance with caller-supplied metadata, and executes it.
        
        :param run_id: PipelineRun UUID or None to use instance run_id
        :param step_key: Step identifier from steps registry
        :param payload: Input data for step execution
        :param order_index: Caller-supplied observational step position
        :param parent_ids: Optional lineage metadata for prior step IDs
        :param agent_config: Optional AgentConfig override
        :return: Step output payload
        :raises ValueError: If run_id missing or step not registered
        """
        # Use instance run_id if not explicitly provided

        if run_id is None:
            run_id = self.run_id

        # Ensure run_id is available

        if run_id is None:
            raise ValueError("run_id is required to execute a step")

        # Validate step key in compatibility map

        if step_key not in self.steps:
            raise ValueError(f"Step '{step_key}' not registered in Pipeline '{self.name}'")

        # Retrieve step class for compatibility lookup

        step_cls = self.steps[step_key]

        # Instantiate step with lineage metadata only

        step = step_cls(
            run_id=run_id,
            name=step_key,
            payload=payload,
            order_index=order_index,
            parent_ids=parent_ids,
            agent_config=agent_config,
        )

        # Execute step and return results

        return step.run()

    @classmethod
    def mark_success(cls, run_id: str):
        """
        Ledger lifecycle helper to mark a run succeeded.

        This records terminal run status only.
        Orchestration completion decisions are external.

        TODO: Preserve compatibility for existing activity callers.

        :param run_id: UUID of PipelineRun to update
        """
        run = PipelineRun.objects.get(pk=run_id)
        run.mark_succeeded()

    @classmethod
    def mark_failure(cls, run_id: str, error: Optional[str] = None):
        """
        Ledger lifecycle helper to mark a run failed.

        This records terminal run status only.
        Failure handling policy remains caller-owned.

        TODO: Preserve compatibility for existing activity callers.

        :param run_id: UUID of PipelineRun to update
        :param error: Optional error message (not currently stored)
        """
        run = PipelineRun.objects.get(pk=run_id)
        run.mark_failed()


class PipelineRegistry:
    """
    Compatibility registry for pipeline definition lookup.

    Provides centralized registration and retrieval for legacy callers.
    This registry does not own step orchestration decisions.

    TODO: Remove after caller migration to direct resolution.
    """

    _pipelines: Dict[str, Type[Pipeline]] = {}

    @classmethod
    def register(cls, pipeline_cls: Type[Pipeline]):
        """
        Register a Pipeline class in the compatibility registry.

        Registration supports legacy lookup integration paths only.

        TODO: Replace with future definition-loading boundary.

        :param pipeline_cls: Pipeline subclass to register
        :raises ValueError: If pipeline has no name attribute
        """
        # Validate pipeline has required name attribute

        if not pipeline_cls.name:
            raise ValueError(f"Pipeline {pipeline_cls.__name__} must have a 'name'.")

        # Store in registry by name

        cls._pipelines[pipeline_cls.name] = pipeline_cls

    @classmethod
    def get(cls, name: str) -> Type[Pipeline]:
        """
        Resolve a Pipeline class from compatibility registry lookup.

        This lookup is a compatibility bridge for existing callers.

        TODO: Remove when callers stop using registry resolution.

        :param name: Pipeline name identifier
        :return: Pipeline class
        :raises ValueError: If pipeline name not found in registry
        """
        # Validate pipeline exists

        if name not in cls._pipelines:
            raise ValueError(f"Pipeline '{name}' not found in registry.")

        # Return pipeline class

        return cls._pipelines[name]
