from datetime import timedelta
from typing import Optional, Sequence

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.temporal.activities import mark_pipeline_failed_activity


class WorkflowExecutionHelpers:
    """
    Shared helper methods for pipeline workflow implementations.

    These helpers keep common payload handling and failure reporting
    in one reusable location while concrete workflows own orchestration.
    """

    @staticmethod
    def extract_run_payload(payload: dict) -> tuple[Optional[str], dict]:
        """
        Extract run_id and nested step payload from workflow input.

        :param payload: Workflow input payload dictionary.
        :return: Tuple of optional run_id and normalized payload.
        :raises ValueError: If payload is not a dictionary.
        """
        if not isinstance(payload, dict):
            raise ValueError("Workflow payload must be a dict")

        if isinstance(payload.get("payload"), dict):
            step_payload = payload["payload"]
        else:
            step_payload = dict(payload)

        run_id = payload.get("run_id") or step_payload.pop("run_id", None)
        return run_id, step_payload

    @staticmethod
    def needs_keyword_sync(values: Sequence[str], trigger_keywords: Sequence[str]) -> bool:
        """
        Check whether any values include sync-trigger keywords.

        :param values: Category or label values to inspect.
        :param trigger_keywords: Case-insensitive trigger keywords.
        :return: True when at least one trigger keyword matches.
        """
        for value in values:
            value_lower = value.lower()
            if any(keyword in value_lower for keyword in trigger_keywords):
                return True
        return False

    @staticmethod
    async def fail_workflow(
        run_id: str,
        pipeline_name: str,
        stage: str,
        error: Exception,
    ) -> None:
        """
        Mark a workflow run as failed with stage context.

        :param run_id: Pipeline run identifier.
        :param pipeline_name: Pipeline name for lifecycle marking.
        :param stage: Workflow stage where failure occurred.
        :param error: Captured exception instance.
        :return: None.
        """
        workflow.logger.error(f"Workflow {pipeline_name} failed at {stage}: {error}")
        await workflow.execute_activity(
            mark_pipeline_failed_activity,
            args=[run_id, pipeline_name, f"Stage: {stage}. Error: {str(error)}"],
            start_to_close_timeout=timedelta(seconds=10),
        )
