from __future__ import annotations

import asyncio

import pytest

from agents.adapters.temporal.workflows import WorkflowExecutionHelpers


def test_extract_run_payload_with_nested_payload() -> None:
    run_id, payload = WorkflowExecutionHelpers.extract_run_payload(
        {
            "run_id": "root-run",
            "payload": {
                "run_id": "nested-run",
                "x": 1,
            },
        }
    )

    assert run_id == "root-run"
    assert payload == {"run_id": "nested-run", "x": 1}


def test_extract_run_payload_without_nested_payload() -> None:
    run_id, payload = WorkflowExecutionHelpers.extract_run_payload(
        {"run_id": "abc", "text": "hello"}
    )

    assert run_id == "abc"
    assert payload == {"run_id": "abc", "text": "hello"}


def test_extract_run_payload_requires_dict() -> None:
    with pytest.raises(ValueError, match="must be a dict"):
        WorkflowExecutionHelpers.extract_run_payload("bad")


def test_needs_keyword_sync_is_case_insensitive() -> None:
    assert WorkflowExecutionHelpers.needs_keyword_sync(
        ["Meeting Notes", "Other"],
        ["meeting", "project"],
    )
    assert not WorkflowExecutionHelpers.needs_keyword_sync(
        ["General update"],
        ["meeting", "project"],
    )


def test_fail_workflow_executes_failure_activity(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_execute_activity(activity_callable, args, start_to_close_timeout):
        calls.append(
            {
                "callable": activity_callable,
                "args": args,
                "timeout": start_to_close_timeout,
            }
        )

    class DummyLogger:
        def error(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("agents.adapters.temporal.workflows.workflow.logger", DummyLogger())
    monkeypatch.setattr("agents.adapters.temporal.workflows.workflow.execute_activity", fake_execute_activity)

    asyncio.run(
        WorkflowExecutionHelpers.fail_workflow(
            run_id="run-44",
            pipeline_name="demo.pipeline",
            stage="step-1",
            error=RuntimeError("boom"),
        )
    )

    assert len(calls) == 1
    assert calls[0]["args"][0] == "run-44"
    assert calls[0]["args"][1] == "demo.pipeline"
    assert "step-1" in calls[0]["args"][2]
