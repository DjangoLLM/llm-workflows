from __future__ import annotations

import pytest

from agents.models import PipelineRun, PipelineStatus, PipelineStep as PipelineStepModel
from agents.core.pipeline_structure import Pipeline, PipelineRegistry, PipelineStep


class EchoStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        return {"echo": payload}


class ErrorStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        raise RuntimeError("step failed")


class PreprocessingErrorStep(PipelineStep):
    def pre_execute(self, payload: dict, context: dict | None = None) -> dict:
        raise ValueError("preprocessing failed")


class DemoPipeline(Pipeline):
    name = "demo.pipeline"
    steps = {
        "echo": EchoStep,
        "error": ErrorStep,
        "preprocessing_error": PreprocessingErrorStep,
    }


@pytest.mark.django_db
def test_execute_step_success_updates_ledger() -> None:
    pipeline = DemoPipeline(payload={"root": True})

    result = pipeline.execute_step(
        run_id=None,
        step_key="echo",
        payload={"x": 1},
        order_index=0,
    )

    run = PipelineRun.objects.get(pk=pipeline.run_id)
    step = PipelineStepModel.objects.get(run=run, step_name="echo")

    assert result == {"echo": {"x": 1}}
    assert step.status == PipelineStatus.SUCCEEDED
    assert step.output_payload == {"echo": {"x": 1}}
    assert run.status == PipelineStatus.RUNNING
    assert run.current_step == "echo"


@pytest.mark.django_db
def test_execute_step_persists_parent_lineage() -> None:
    pipeline = DemoPipeline(payload={"root": True})

    pipeline.execute_step(
        run_id=None,
        step_key="echo",
        payload={"generation": 1},
        order_index=0,
    )
    run = PipelineRun.objects.get(pk=pipeline.run_id)
    parent = PipelineStepModel.objects.get(run=run, order_index=0)

    pipeline.execute_step(
        run_id=None,
        step_key="echo",
        payload={"generation": 2},
        order_index=1,
        parent_ids=[str(parent.id).upper()],
    )

    child = PipelineStepModel.objects.get(run=run, order_index=1)
    assert list(child.parents.values_list("id", flat=True)) == [parent.id]


@pytest.mark.django_db
def test_execute_step_rejects_parent_from_another_run() -> None:
    source_pipeline = DemoPipeline(payload={"source": True})
    source_pipeline.execute_step(
        run_id=None,
        step_key="echo",
        payload={"generation": 1},
        order_index=0,
    )
    source_run = PipelineRun.objects.get(pk=source_pipeline.run_id)
    foreign_parent = PipelineStepModel.objects.get(run=source_run, order_index=0)
    target_pipeline = DemoPipeline(payload={"target": True})

    with pytest.raises(ValueError, match="must belong to pipeline run"):
        target_pipeline.execute_step(
            run_id=None,
            step_key="echo",
            payload={"generation": 2},
            order_index=0,
            parent_ids=[str(foreign_parent.id)],
        )

    assert not PipelineStepModel.objects.filter(run_id=target_pipeline.run_id).exists()


@pytest.mark.django_db
def test_execute_step_failure_marks_step_failed() -> None:
    pipeline = DemoPipeline(payload={"root": True})

    with pytest.raises(RuntimeError, match="step failed"):
        pipeline.execute_step(
            run_id=None,
            step_key="error",
            payload={"x": 1},
            order_index=1,
        )

    run = PipelineRun.objects.get(pk=pipeline.run_id)
    step = PipelineStepModel.objects.get(run=run, step_name="error")
    assert step.status == PipelineStatus.FAILED
    assert "step failed" in (step.error_message or "")


@pytest.mark.django_db
def test_preprocessing_failure_marks_step_failed() -> None:
    pipeline = DemoPipeline(payload={"root": True})

    with pytest.raises(ValueError, match="preprocessing failed"):
        pipeline.execute_step(
            run_id=None,
            step_key="preprocessing_error",
            payload={"x": 1},
            order_index=2,
        )

    run = PipelineRun.objects.get(pk=pipeline.run_id)
    step = PipelineStepModel.objects.get(run=run, step_name="preprocessing_error")
    assert step.status == PipelineStatus.FAILED
    assert step.error_message == "preprocessing failed"
    assert step.ended_at is not None


@pytest.mark.django_db
def test_execute_step_requires_run_id() -> None:
    pipeline = DemoPipeline(payload={"root": True})
    pipeline.run_id = None

    with pytest.raises(ValueError, match="run_id is required"):
        pipeline.execute_step(
            run_id=None,
            step_key="echo",
            payload={"x": 1},
            order_index=0,
        )


def test_execute_step_rejects_unknown_step_key() -> None:
    pipeline = DemoPipeline(payload={"root": True}, run_id="fake")

    with pytest.raises(ValueError, match="not registered"):
        pipeline.execute_step(
            run_id="fake",
            step_key="missing",
            payload={"x": 1},
            order_index=0,
        )


def test_pipeline_registry_register_and_get() -> None:
    PipelineRegistry.register(DemoPipeline)

    resolved = PipelineRegistry.get("demo.pipeline")

    assert resolved is DemoPipeline


def test_pipeline_registry_rejects_missing_name() -> None:
    class InvalidPipeline(Pipeline):
        name = ""
        steps = {}

    with pytest.raises(ValueError, match="must have a 'name'"):
        PipelineRegistry.register(InvalidPipeline)


def test_pipeline_registry_rejects_unknown_lookup() -> None:
    with pytest.raises(ValueError, match="not found in registry"):
        PipelineRegistry.get("does.not.exist")
