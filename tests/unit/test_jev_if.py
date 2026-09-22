from __future__ import annotations

import pytest
from agents.runner.choice import CRITERIA, HEAD, JevIf, collapse
from agents.adapters.temporal import activities

RAW = {
    "choices": {HEAD: "true"},
    "confidence": {HEAD: 0.9},
    "probabilities": {HEAD: {"true": 0.9, "false": 0.1}},
    "model": "jev-latest",
    "usage": {},
}


def test_runner_is_a_two_way_jev_head() -> None:
    runner = JevIf("The segment refers to a tracked task.", model="jev-latest").runner
    assert runner.adapter.instructions == "The segment refers to a tracked task."
    assert runner.adapter.model == "jev-latest"
    assert runner.adapter.questions == {HEAD: {"criteria": CRITERIA}}


def test_empty_condition_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        JevIf("")


@pytest.mark.django_db
def test_choice_runner_preserves_managed_output(monkeypatch):
    from types import SimpleNamespace
    from agents.models import AgentRun, AgentRunStatus

    monkeypatch.setattr(
        "agents.adapters.inference.jev.JevRunner.run_sync",
        lambda self, payload: SimpleNamespace(output=RAW),
    )
    assert JevIf("Is this a task?").decide({"text": "Fix login"})["result"] is True
    run = AgentRun.objects.get()
    assert run.status == AgentRunStatus.SUCCEEDED
    assert run.output == RAW


@pytest.mark.django_db
def test_choice_runner_preserves_managed_failure(monkeypatch):
    from agents.models import AgentRun, AgentRunStatus

    def fail(self, payload):
        raise ValueError("invalid selection")

    monkeypatch.setattr("agents.adapters.inference.jev.JevRunner.run_sync", fail)
    with pytest.raises(RuntimeError, match="invalid selection"):
        JevIf("Is this a task?").decide({})
    assert AgentRun.objects.get().status == AgentRunStatus.FAILED


@pytest.mark.parametrize("choice, expected", [("true", True), ("false", False)])
def test_collapse_turns_choice_into_bool(choice: str, expected: bool) -> None:
    assert collapse({**RAW, "choices": {HEAD: choice}}) == {
        "result": expected,
        "confidence": 0.9,
        "probabilities": {"true": 0.9, "false": 0.1},
    }


def test_activity_builds_jev_if_and_decides(monkeypatch) -> None:
    seen = {}

    def fake_decide(self, state):
        seen.update(condition=self.condition, model=self.model, label=self.label, state=state)
        return {"result": True, "confidence": 0.9, "probabilities": {"true": 0.9, "false": 0.1}}

    monkeypatch.setattr(JevIf, "decide", fake_decide)
    out = activities.jev_if_activity("Is a task?", {"text": "fix login"}, "jev-latest")
    assert out["result"] is True
    assert seen == {"condition": "Is a task?", "model": "jev-latest", "label": "jev_if", "state": {"text": "fix login"}}
