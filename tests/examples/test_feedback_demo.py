from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

DEMO_DIR = Path(__file__).resolve().parents[2] / "examples" / "feedback_demo"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

from agents.models import AgentRun, AgentRunStatus, PipelineRun, PipelineStatus, PipelineStep
from agents.core.pipeline_structure import PipelineRegistry
from agents.core.step_catalog import StepCatalog, StepExecutionType
from feedback.pipelines import (
    ANALYZE_STEP,
    CLEAN_STEP,
    PIPELINE_NAME,
    FeedbackPipeline,
    register_feedback_pipeline,
)
from feedback.temporal_plugin import get_temporal_worker_plugin
from feedback.views import run_status, start


def test_feedback_pipeline_registration() -> None:
    register_feedback_pipeline()

    assert PipelineRegistry.get(PIPELINE_NAME) is FeedbackPipeline
    assert StepCatalog.get_step(CLEAN_STEP).execution_type == StepExecutionType.CODE
    assert StepCatalog.get_step(ANALYZE_STEP).execution_type == StepExecutionType.LLM


def test_feedback_temporal_plugin_registers_pipeline_before_building() -> None:
    plugin = get_temporal_worker_plugin()

    assert plugin.plugin_slug == "feedback"
    assert plugin.workflows
    assert StepCatalog.get_step(CLEAN_STEP).pipeline_name == PIPELINE_NAME
    analyze_registration = StepCatalog.get_step(ANALYZE_STEP)
    assert analyze_registration.pipeline_name == PIPELINE_NAME
    analyze_step = analyze_registration.step_class.__new__(analyze_registration.step_class)
    assert analyze_step.agent_config.result_type is dict


@pytest.mark.django_db
def test_run_status_serializes_steps_and_agent_run() -> None:
    run = PipelineRun.create_run(
        pipeline_name=PIPELINE_NAME,
        root_payload={"text": "Great onboarding, confusing invoice."},
    )
    PipelineStep.create_step(
        run=run,
        step_name=CLEAN_STEP,
        order_index=0,
        input_payload={"text": "Great onboarding, confusing invoice."},
    ).mark_finished(
        PipelineStatus.SUCCEEDED,
        output_payload={"cleaned_text": "great onboarding, confusing invoice."},
    )
    agent_run = AgentRun.objects.create(
        agent_label=ANALYZE_STEP,
        status=AgentRunStatus.SUCCEEDED,
        input={"cleaned_text": "great onboarding, confusing invoice."},
        output={"sentiment": "neutral", "action_item": "Improve invoices."},
    )
    PipelineStep.create_step(
        run=run,
        step_name=ANALYZE_STEP,
        order_index=1,
        input_payload={"cleaned_text": "great onboarding, confusing invoice."},
        agent_run=agent_run,
    ).mark_finished(
        PipelineStatus.SUCCEEDED,
        output_payload={"sentiment": "neutral", "action_item": "Improve invoices."},
    )
    run.mark_succeeded()

    request = RequestFactory().get(f"/runs/{run.id}/status/")
    response = run_status(request, str(run.id))
    payload = json.loads(response.content)

    assert payload["run"]["status"] == PipelineStatus.SUCCEEDED
    assert [step["step_name"] for step in payload["steps"]] == [CLEAN_STEP, ANALYZE_STEP]
    assert payload["steps"][1]["agent_run"]["status"] == AgentRunStatus.SUCCEEDED
    assert payload["final_output"] == {"sentiment": "neutral", "action_item": "Improve invoices."}
    assert payload["is_terminal"] is True


@pytest.mark.django_db
def test_start_view_validates_feedback_text() -> None:
    request = RequestFactory().post("/start/", {"feedback_text": "   "})

    response = start(request)

    assert response.status_code == 400
    assert PipelineRun.objects.count() == 0


@pytest.mark.django_db
def test_start_view_creates_run_and_starts_temporal(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_start_feedback_workflow(run_id: str, text: str) -> None:
        calls.append((run_id, text))

    def fake_redirect(route_name: str, **kwargs) -> HttpResponse:
        response = HttpResponse(status=302)
        response["X-Route-Name"] = route_name
        response["X-Run-Id"] = str(kwargs["run_id"])
        return response

    monkeypatch.setattr("feedback.views._start_feedback_workflow", fake_start_feedback_workflow)
    monkeypatch.setattr("feedback.views.redirect", fake_redirect)

    request = RequestFactory().post("/start/", {"feedback_text": " The product works well. "})
    response = start(request)

    run = PipelineRun.objects.get()
    assert response.status_code == 302
    assert response["X-Route-Name"] == "feedback:run_detail"
    assert response["X-Run-Id"] == str(run.id)
    assert calls == [(str(run.id), "The product works well.")]
    assert run.root_payload == {"text": "The product works well."}
