from __future__ import annotations

import pytest

from agents.models import AgentRun, AgentRunStatus, PipelineRun, PipelineStatus, PipelineStep


@pytest.mark.django_db
def test_pipeline_run_lifecycle_methods() -> None:
    run = PipelineRun.create_run("demo.pipeline", root_payload={"root": True}, context={"a": 1})

    assert run.status == PipelineStatus.PENDING
    assert run.context == {"a": 1}
    assert run.root_payload == {"root": True}

    run.set_running("step.one")
    run.refresh_from_db()
    assert run.status == PipelineStatus.RUNNING
    assert run.current_step == "step.one"

    run.mark_failed("step.two")
    run.refresh_from_db()
    assert run.status == PipelineStatus.FAILED
    assert run.current_step == "step.two"

    run.mark_succeeded()
    run.refresh_from_db()
    assert run.status == PipelineStatus.SUCCEEDED
    assert run.current_step is None

    run.update_context({"changed": True})
    run.refresh_from_db()
    assert run.context == {"changed": True}


@pytest.mark.django_db
def test_pipeline_step_lifecycle_methods() -> None:
    run = PipelineRun.create_run("demo.pipeline")
    agent_run = AgentRun.objects.create(agent_label="x", status=AgentRunStatus.PENDING)

    step = PipelineStep.create_step(
        run=run,
        step_name="step.one",
        order_index=1,
        input_payload={"v": 1},
        agent_run=agent_run,
    )

    assert step.status == PipelineStatus.PENDING
    assert step.input_payload == {"v": 1}
    assert step.agent_run_id == agent_run.id

    step.mark_running()
    step.refresh_from_db()
    assert step.status == PipelineStatus.RUNNING
    assert step.started_at is not None

    step.mark_finished(PipelineStatus.SUCCEEDED, output_payload={"done": True})
    step.refresh_from_db()
    assert step.status == PipelineStatus.SUCCEEDED
    assert step.output_payload == {"done": True}
    assert step.error_message is None
    assert step.ended_at is not None
