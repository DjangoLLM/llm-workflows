from __future__ import annotations

import asyncio

import pytest
from agents.adapters.inference.jev import JevRunner

QUESTIONS = {"category": {"criteria": {"meeting": "Meeting notes", "task": "Status update or task"}}}


def _runner(**overrides) -> JevRunner:
    return JevRunner(instructions="Pick the category.", questions=QUESTIONS, **overrides)


def test_jev_runner_requires_questions_with_criteria() -> None:
    with pytest.raises(ValueError, match="requires `questions`"):
        JevRunner(instructions="x", questions={})
    with pytest.raises(ValueError, match="requires `questions`"):
        JevRunner(instructions="x", questions={"h": {"instructions": {}}})


def test_jev_runner_returns_validated_choices(monkeypatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    sent = {}

    def fake_post(body, key):
        sent.update(body=body, key=key)
        return {
            "model": "jev-latest",
            "answers": {"category": {"choice": "task", "confidence": 0.8, "probabilities": {"meeting": 0.2, "task": 0.8}}},
        }

    monkeypatch.setattr("agents.adapters.inference.jev.post_json", fake_post)
    runner = _runner(model="jev-latest")

    result = runner.run_sync({"segment_text": "fix the login bug"})

    assert result.output["choices"] == {"category": "task"}
    assert result.output["confidence"] == {"category": 0.8}
    assert sent["key"] == "k"
    assert sent["body"]["state"] == {"segment_text": "fix the login bug"}
    assert sent["body"]["questions"]["category"] == {
        "type": "choice",
        "instructions": {"goal": "Pick the category."},
        "criteria": QUESTIONS["category"]["criteria"],
    }
    assert asyncio.run(runner.run({"segment_text": "x"})).output["choices"] == {"category": "task"}


def test_jev_runner_rejects_choice_outside_offered_ids(monkeypatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setattr(
        "agents.adapters.inference.jev.post_json",
        lambda body, key: {"answers": {"category": {"choice": "other", "confidence": 1, "probabilities": {"other": 1}}}},
    )
    with pytest.raises(ValueError, match="Invalid Jev answer"):
        _runner().run_sync({})


def test_jev_runner_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        _runner().run_sync({})
