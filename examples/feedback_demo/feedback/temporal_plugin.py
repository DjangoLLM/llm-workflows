"""Temporal workflow plugin for the feedback demo pipeline."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

from agents.runner.temporal.worker_plugins import TemporalWorkerPlugin

with workflow.unsafe.imports_passed_through():
    from agents.runner.temporal.activities import (
        create_pipeline_run_activity,
        execute_pipeline_step_activity,
        mark_pipeline_failed_activity,
        mark_pipeline_success_activity,
    )
    from feedback.pipelines import ANALYZE_STEP, CLEAN_STEP, ECHO_STEP, PIPELINE_NAME
    from feedback.pipelines import register_feedback_pipeline


@workflow.defn(name="feedback.pipeline.workflow")
class FeedbackPipelineWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        run_id = payload.get("run_id")
        step_payload = payload.get("payload", payload)

        try:
            if not run_id:
                run_id = await workflow.execute_activity(
                    create_pipeline_run_activity,
                    args=[PIPELINE_NAME, step_payload],
                    start_to_close_timeout=timedelta(seconds=10),
                )

            cleaned_data = await workflow.execute_activity(
                execute_pipeline_step_activity,
                args=[run_id, PIPELINE_NAME, CLEAN_STEP, 0, step_payload],
                start_to_close_timeout=timedelta(minutes=1),
            )

            echo_data = await workflow.execute_activity(
                execute_pipeline_step_activity,
                args=[run_id, PIPELINE_NAME, ECHO_STEP, 1, cleaned_data],
                start_to_close_timeout=timedelta(minutes=1),
            )

            analysis_result = await workflow.execute_activity(
                execute_pipeline_step_activity,
                args=[run_id, PIPELINE_NAME, ANALYZE_STEP, 2, echo_data],
                start_to_close_timeout=timedelta(minutes=2),
            )

            await workflow.execute_activity(
                mark_pipeline_success_activity,
                args=[run_id, PIPELINE_NAME],
                start_to_close_timeout=timedelta(seconds=10),
            )

            return {"run_id": run_id, "output": analysis_result}

        except Exception as exc:
            if run_id:
                await workflow.execute_activity(
                    mark_pipeline_failed_activity,
                    args=[run_id, PIPELINE_NAME, str(exc)],
                    start_to_close_timeout=timedelta(seconds=10),
                )
            raise


def get_temporal_worker_plugin() -> TemporalWorkerPlugin:
    # Ensure the demo pipeline and its step catalog are registered before the
    # Temporal worker composes activities from the catalog.
    register_feedback_pipeline()

    return TemporalWorkerPlugin(
        plugin_slug="feedback",
        workflows=[FeedbackPipelineWorkflow],
        activities=[],
    )
