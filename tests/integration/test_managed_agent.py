from __future__ import annotations

from dataclasses import dataclass

import pytest

from agents import AgentRunStatus, run_agent
from agents.core.agent import ManagedAgent
from agents.handlers import agent_run_completed
from agents.models import AgentRun
from tests.support.stubs import DataclassOutput, FakeAgentFailure, FakeAgentSuccess


class DumpableOutput:
    def __init__(self, value: dict):
        self._value = value

    def model_dump(self) -> dict:
        return self._value


@pytest.mark.django_db
def test_managed_agent_run_sync_success() -> None:
    managed = ManagedAgent(agent=FakeAgentSuccess({"ok": True}), agent_label="demo")

    output = managed.run_sync(input_payload={"a": 1}, pipeline_name="pipe", step_name="step")

    run = AgentRun.objects.get(pk=managed.run_id)
    assert output == {"ok": True}
    assert run.status == AgentRunStatus.SUCCEEDED
    assert run.output == {"ok": True}
    assert run.error_message in (None, "")


@pytest.mark.django_db
def test_managed_agent_run_sync_failure() -> None:
    managed = ManagedAgent(agent=FakeAgentFailure(), agent_label="demo")

    output = managed.run_sync(input_payload={"a": 1})

    run = AgentRun.objects.get(pk=managed.run_id)
    assert output is None
    assert run.status == AgentRunStatus.FAILED
    assert "boom" in (run.error_message or "")


@pytest.mark.django_db
def test_managed_agent_one_shot_guard() -> None:
    managed = ManagedAgent(agent=FakeAgentSuccess({"ok": True}), agent_label="demo")
    managed.run_sync(input_payload={"a": 1})

    with pytest.raises(RuntimeError, match="more than once"):
        managed.run_sync(input_payload={"a": 2})


@pytest.mark.django_db
def test_managed_agent_output_normalization_dataclass() -> None:
    managed = ManagedAgent(agent=FakeAgentSuccess(DataclassOutput(message="hello")), agent_label="demo")

    output = managed.run_sync(input_payload={})

    assert output == {"message": "hello"}


@pytest.mark.django_db
def test_managed_agent_output_normalization_model_dump() -> None:
    managed = ManagedAgent(agent=FakeAgentSuccess(DumpableOutput({"k": "v"})), agent_label="demo")

    output = managed.run_sync(input_payload={})

    assert output == {"k": "v"}


@pytest.mark.django_db
def test_run_async_calls_callback_before_signal(inline_thread) -> None:
    events: list[str] = []

    def callback(_payload):
        events.append("callback")

    def receiver(sender, **kwargs):
        events.append("signal")

    agent_run_completed.connect(receiver)
    try:
        managed = ManagedAgent(agent=FakeAgentSuccess({"ok": True}), agent_label="demo")
        managed.run(input_payload={"a": 1}, pipeline_name="pipe", on_complete=callback)
    finally:
        agent_run_completed.disconnect(receiver)

    assert events[:2] == ["callback", "signal"]


@pytest.mark.django_db
def test_run_agent_helper_persists_and_emits(inline_thread) -> None:
    captured: list[dict] = []

    def receiver(sender, **kwargs):
        captured.append(kwargs)

    agent_run_completed.connect(receiver)
    try:
        run_id = run_agent(
            FakeAgentSuccess({"result": "ok"}),
            input_payload={"hello": "world"},
            agent_label="helper",
            pipeline_name="pipeline",
        )
    finally:
        agent_run_completed.disconnect(receiver)

    run = AgentRun.objects.get(pk=run_id)
    assert run.status == AgentRunStatus.SUCCEEDED
    assert run.output == {"result": "ok"}
    assert captured[0]["pipeline_name"] == "pipeline"
