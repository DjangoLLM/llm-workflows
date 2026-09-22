"""Views for the one-page feedback pipeline demo."""

from __future__ import annotations

import uuid
from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from temporalio.client import Client

from agents.models import AgentRun, PipelineRun, PipelineStatus, PipelineStep
from agents.runner import create_workflow_run

from agents.runner.tools import default_registry

from .pipelines import ANALYZE_STEP, PIPELINE_NAME

WORKFLOW_NAME = "feedback.pipeline.workflow"


async def _start_feedback_workflow(run_id: str, text: str) -> None:
    client = await Client.connect(settings.TEMPORAL_SERVER_URL)
    await client.start_workflow(
        WORKFLOW_NAME,
        {"run_id": run_id, "payload": {"text": text}},
        id=f"feedback-job-{uuid.uuid4()}",
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )


def index(request: HttpRequest, run_id: str | None = None) -> HttpResponse:
    run = None
    if run_id:
        run = PipelineRun.objects.filter(pk=run_id).first()
        if run is None:
            raise Http404("Pipeline run not found.")

    return render(
        request,
        "feedback/index.html",
        {
            "run": run,
            "status_url": reverse("feedback:run_status", args=[run.id]) if run else "",
            "submitted_text": (run.root_payload or {}).get("text", "") if run else "",
        },
    )


def start(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("feedback:index")

    feedback_text = request.POST.get("feedback_text", "").strip()
    if not feedback_text:
        return render(
            request,
            "feedback/index.html",
            {
                "error": "Enter feedback text before starting the pipeline.",
                "submitted_text": request.POST.get("feedback_text", ""),
            },
            status=400,
        )

    run_id = create_workflow_run(PIPELINE_NAME, {"text": feedback_text})

    try:
        async_to_sync(_start_feedback_workflow)(run_id, feedback_text)
    except Exception as exc:  # noqa: BLE001
        run = PipelineRun.objects.get(pk=run_id)
        run.mark_failed("start_workflow")
        return render(
            request,
            "feedback/index.html",
            {
                "error": f"Could not start Temporal workflow: {exc}",
                "run": run,
                "status_url": reverse("feedback:run_status", args=[run.id]),
                "submitted_text": feedback_text,
            },
            status=502,
        )

    return redirect("feedback:run_detail", run_id=run_id)


def run_status(request: HttpRequest, run_id: str) -> JsonResponse:
    run = PipelineRun.objects.filter(pk=run_id).first()
    if run is None:
        raise Http404("Pipeline run not found.")

    steps = list(
        PipelineStep.objects.filter(run=run)
        .select_related("agent_run")
        .order_by("order_index", "created_at")
    )
    final_step = next(
        (
            step
            for step in reversed(steps)
            if step.step_name == ANALYZE_STEP and step.status == PipelineStatus.SUCCEEDED
        ),
        None,
    )
    first_error = next((step.error_message for step in steps if step.error_message), None)

    return JsonResponse(
        {
            "run": _serialize_run(run),
            "steps": [_serialize_step(step) for step in steps],
            "final_output": final_step.output_payload if final_step else None,
            "error": first_error,
            "is_terminal": run.status in {PipelineStatus.SUCCEEDED, PipelineStatus.FAILED},
        }
    )


def tool_playground(request: HttpRequest) -> HttpResponse:
    tools = []
    for name in default_registry.names():
        descriptor = default_registry.get(name)
        tools.append(
            {
                "name": name,
                "toolset": descriptor.toolset_name,
                "mcp_safe": descriptor.mcp_safe,
                "input_fields": list(descriptor.input_model.model_fields.keys()),
            }
        )
    return render(request, "feedback/tool_playground.html", {"tools": tools})


def tool_invoke(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    import json

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as exc:
        return JsonResponse({"error": f"Invalid JSON: {exc}"}, status=400)

    tool_name = body.get("tool")
    input_data = body.get("input", {})

    if not tool_name:
        return JsonResponse({"error": "Missing 'tool' field"}, status=400)

    try:
        result = default_registry.run(tool_name, input_data)
    except KeyError:
        return JsonResponse({"error": f"Unknown tool: {tool_name!r}"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=422)

    return JsonResponse({"tool": tool_name, "input": input_data, "output": result.model_dump()})


def _serialize_run(run: PipelineRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "pipeline_name": run.pipeline_name,
        "status": run.status,
        "current_step": run.current_step,
        "root_payload": run.root_payload,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _serialize_step(step: PipelineStep) -> dict[str, Any]:
    return {
        "id": str(step.id),
        "step_name": step.step_name,
        "order_index": step.order_index,
        "status": step.status,
        "input_payload": step.input_payload,
        "output_payload": step.output_payload,
        "error_message": step.error_message,
        "started_at": step.started_at,
        "ended_at": step.ended_at,
        "agent_run": _serialize_agent_run(step.agent_run) if step.agent_run else None,
    }


def _serialize_agent_run(agent_run: AgentRun) -> dict[str, Any]:
    return {
        "id": str(agent_run.id),
        "agent_label": agent_run.agent_label,
        "status": agent_run.status,
        "input": agent_run.input,
        "output": agent_run.output,
        "error_message": agent_run.error_message,
        "started_at": agent_run.started_at,
        "ended_at": agent_run.ended_at,
    }
