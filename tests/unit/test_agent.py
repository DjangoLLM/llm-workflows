from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest

from agents.agent import Agent, AgentConfig


def _patch_openai_model_construction(monkeypatch) -> None:
    monkeypatch.setattr("agents.agent.OpenAIResponsesModel", lambda model: f"model:{model}")
    monkeypatch.setattr(
        "agents.agent.OpenAIResponsesModelSettings",
        lambda **kwargs: {"settings": kwargs},
    )


def test_agent_requires_config_or_default(settings) -> None:
    settings.DEFAULT_AGENT_CONFIG = None

    with pytest.raises(ValueError, match="DEFAULT_AGENT_CONFIG"):
        Agent()


def test_agent_uses_explicit_config_with_string_model(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.agent.PydanticAgent") as pydantic_agent:
        Agent(config=AgentConfig(instructions="test", model="gpt-5-mini"))

    assert pydantic_agent.call_count == 1


def test_agent_builds_config_from_kwargs(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.agent.PydanticAgent") as pydantic_agent:
        Agent(instructions="from kwargs", model="gpt-5-mini")

    assert pydantic_agent.call_count == 1


def test_agent_run_sync_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.agent.PydanticAgent"):
        agent = Agent(config=AgentConfig(instructions="x"))

    fake = mock.Mock()
    fake.run_sync.return_value = SimpleNamespace(output={"ok": True})
    agent._pydantic_agent = fake

    result = agent.run_sync({"a": 1})

    assert result.output == {"ok": True}
    fake.run_sync.assert_called_once_with('{"a": 1}')


def test_agent_run_async_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.agent.PydanticAgent"):
        agent = Agent(config=AgentConfig(instructions="x"))

    class FakeAsync:
        async def run(self, payload):
            assert payload == '{"b": 2}'
            return SimpleNamespace(output={"ok": True})

    agent._pydantic_agent = FakeAsync()

    result = asyncio.run(agent.run({"b": 2}))

    assert result.output == {"ok": True}
