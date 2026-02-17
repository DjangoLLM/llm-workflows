import logging
from typing import Callable, Dict

from temporalio import activity

from agents.pipeline_structure import PipelineRegistry
from agents.step_catalog import StepCatalog

logger = logging.getLogger(__name__)


@activity.defn(name="agents.create_pipeline_run_activity")
def create_pipeline_run_activity(pipeline_name: str, payload: dict) -> str:
    """Delegates run record creation to the Pipeline Service."""
    pipeline_cls = PipelineRegistry.get(pipeline_name)
    run_id = pipeline_cls.create_run(payload)
    logger.info(f"Created PipelineRun {run_id} via {pipeline_name} Service")
    return run_id


@activity.defn(name="agents.execute_pipeline_step_activity")
def execute_pipeline_step_activity(
    run_id: str,
    pipeline_name: str,
    step_key: str,
    order_index: int,
    payload: dict,
) -> dict:
    """
    Executes a specific step within a pipeline service.

    The catalog resolves metadata and delegates execution to the
    existing pipeline runtime path.
    """
    logger.info(f"Executing step '{step_key}' for pipeline {pipeline_name} (Run: {run_id})")
    return StepCatalog.execute_step(
        run_id=run_id,
        pipeline_name=pipeline_name,
        step_key=step_key,
        order_index=order_index,
        payload=payload,
    )


_TRANSFORMED_STEP_ACTIVITIES: Dict[str, Callable[..., dict]] = {}


def _activity_safe_step_name(step_key: str) -> str:
    """
    Build stable activity-safe names from step keys.

    :param step_key: Registered step key.
    :return: Deterministic activity name suffix.
    """
    return step_key.replace(".", "_").replace("-", "_")


def transform_step_to_activity(step_key: str) -> Callable[..., dict]:
    """
    Transform one registered step key into an activity callable.

    :param step_key: Registered step key.
    :return: Temporal-compatible activity function.
    :raises ValueError: If step key is not registered.
    """
    StepCatalog.get_step(step_key)
    if step_key in _TRANSFORMED_STEP_ACTIVITIES:
        return _TRANSFORMED_STEP_ACTIVITIES[step_key]

    safe_key = _activity_safe_step_name(step_key)
    activity_name = f"agents.pipeline_step.{step_key}"

    # Capture key in closure for deterministic dispatch.

    @activity.defn(name=activity_name)
    def _generated_step_activity(
        run_id: str,
        pipeline_name: str,
        order_index: int,
        payload: dict,
    ) -> dict:
        return execute_pipeline_step_activity(
            run_id=run_id,
            pipeline_name=pipeline_name,
            step_key=step_key,
            order_index=order_index,
            payload=payload,
        )

    _generated_step_activity.__name__ = f"{safe_key}_step_activity"
    _generated_step_activity.__qualname__ = _generated_step_activity.__name__
    _TRANSFORMED_STEP_ACTIVITIES[step_key] = _generated_step_activity
    return _generated_step_activity


def get_registered_step_activities() -> list[Callable[..., dict]]:
    """
    Return transformed activities for registered steps.

    :return: List of activity callables.
    """
    activities: list[Callable[..., dict]] = []
    for step_key in StepCatalog.list_step_keys():
        activities.append(transform_step_to_activity(step_key))
    return activities


@activity.defn(name="agents.mark_pipeline_success_activity")
def mark_pipeline_success_activity(run_id: str, pipeline_name: str) -> None:
    """Delegates success marking to the Pipeline Service."""
    pipeline_cls = PipelineRegistry.get(pipeline_name)
    pipeline_cls.mark_success(run_id)

@activity.defn(name="agents.mark_pipeline_failed_activity")
def mark_pipeline_failed_activity(run_id: str, pipeline_name: str, error_message: str) -> None:
    """Delegates failure marking to the Pipeline Service."""
    pipeline_cls = PipelineRegistry.get(pipeline_name)
    pipeline_cls.mark_failure(run_id, error=error_message)


@activity.defn(name="agents.handle_meeting_notes_activity")
async def handle_meeting_notes_activity(run_id: str, payload: dict) -> dict:
    logger.info(f"Stub handler called for Meeting Notes (Run: {run_id})")
    return {"status": "stub_success", "handler": "handle_meeting_notes"}


@activity.defn(name="agents.handle_module_creation_activity")
async def handle_module_creation_activity(run_id: str, payload: dict) -> dict:
    logger.info(f"Stub handler called for Module Creation (Run: {run_id})")
    return {"status": "stub_success", "handler": "handle_module_creation"}

@activity.defn(name="agents.handle_status_update_activity")
async def handle_status_update_activity(run_id: str, payload: dict) -> dict:
    logger.info(f"Stub handler called for Status Update (Run: {run_id})")
    return {"status": "stub_success", "handler": "handle_status_update"}

@activity.defn(name="agents.handle_random_brain_dump_activity")
async def handle_random_brain_dump_activity(run_id: str, payload: dict) -> dict:
    logger.info(f"Stub handler called for Random Brain Dump (Run: {run_id})")
    return {"status": "stub_success", "handler": "handle_random_brain_dump"}
