from __future__ import annotations

import asyncio

import pytest
from agents.core import AgentConfig
from agents.runner import Agent

QUESTIONS = {"category": {"criteria": {"meeting": "Meeting notes", "task": "Status update or task"}}}


def _config(**overrides) -> AgentConfig:
    return AgentConfig(instructions="Pick the category.", execution_backend="jev", questions=QUESTIONS, **overrides)


def test_jev_config_requires_questions_with_criteria() -> None:
    with pytest.raises(ValueError, match="requires `questions`"):
        AgentConfig(instructions="x", execution_backend="jev")
    with pytest.raises(ValueError, match="requires `questions`"):
        AgentConfig(instructions="x", execution_backend="jev", questions={"h": {"instructions": {}}})


def test_jev_agent_skips_pydantic_and_returns_validated_choices(monkeypatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    sent = {}

    def fake_post(body, key):
        sent.update(body=body, key=key)
        return {
            "model": "jev-latest",
            "answers": {"category": {"choice": "task", "confidence": 0.8, "probabilities": {"meeting": 0.2, "task": 0.8}}},
        }

    monkeypatch.setattr("agents.runner.backends.jev.post_json", fake_post)
    agent = Agent(config=_config(model="jev-latest"))
    assert agent._pydantic_agent is None

    result = agent.run_sync({"segment_text": "fix the login bug"})

    assert result.output["choices"] == {"category": "task"}
    assert result.output["confidence"] == {"category": 0.8}
    assert sent["key"] == "k"
    assert sent["body"]["state"] == {"segment_text": "fix the login bug"}
    assert sent["body"]["questions"]["category"] == {
        "type": "choice",
        "instructions": {"goal": "Pick the category."},
        "criteria": QUESTIONS["category"]["criteria"],
    }
    assert asyncio.run(agent.run({"segment_text": "x"})).output["choices"] == {"category": "task"}


def test_jev_agent_rejects_choice_outside_offered_ids(monkeypatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setattr(
        "agents.runner.backends.jev.post_json",
        lambda body, key: {"answers": {"category": {"choice": "other", "confidence": 1, "probabilities": {"other": 1}}}},
    )
    with pytest.raises(ValueError, match="Invalid Jev answer"):
        Agent(config=_config()).run_sync({})


def test_jev_agent_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        Agent(config=_config()).run_sync({})
