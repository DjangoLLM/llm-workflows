from __future__ import annotations

import asyncio
import enum
import uuid
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from agents.core import AgentConfig
from agents.runner import Agent
from agents.core.json_safe import json_safe as _json_safe_value


class DemoEnum(enum.Enum):
    VALUE = "value"


@dataclass
class DemoData:
    value: int


def _patch_openai_model_construction(monkeypatch) -> None:
    monkeypatch.setattr("agents.runner.agent.OpenAIResponsesModel", lambda model: f"model:{model}")
    monkeypatch.setattr(
        "agents.runner.agent.OpenAIResponsesModelSettings",
        lambda **kwargs: {"settings": kwargs},
    )


def test_agent_requires_config_or_default(settings) -> None:
    settings.DEFAULT_AGENT_CONFIG = None

    with pytest.raises(ValueError, match="DEFAULT_AGENT_CONFIG"):
        Agent()


def test_agent_uses_explicit_config_with_string_model(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.runner.agent.PydanticAgent") as pydantic_agent:
        Agent(config=AgentConfig(instructions="test", model="gpt-5-mini"))

    assert pydantic_agent.call_count == 1


def test_agent_builds_config_from_kwargs(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.runner.agent.PydanticAgent") as pydantic_agent:
        Agent(instructions="from kwargs", model="gpt-5-mini")

    assert pydantic_agent.call_count == 1


def test_agent_builds_codex_backend_from_kwargs() -> None:
    runner = mock.Mock()
    with mock.patch(
        "agents.runner.backends.codex.CodexRunner.from_config", return_value=runner
    ) as from_config:
        agent = Agent(
            instructions="typed",
            execution_backend="codex_cli",
            result_type=DemoData,
        )

    assert agent._runner is runner
    assert agent._pydantic_agent is None
    assert from_config.call_args.args[0].execution_backend == "codex_cli"


def test_agent_uses_configured_codex_default(settings) -> None:
    configured = AgentConfig(
        instructions="typed",
        execution_backend="codex_cli",
        result_type=DemoData,
    )
    settings.DEFAULT_AGENT_CONFIG = configured
    runner = mock.Mock()

    with mock.patch(
        "agents.runner.backends.codex.CodexRunner.from_config", return_value=runner
    ):
        agent = Agent()

    assert agent.config is configured
    assert agent._runner is runner


def test_agent_run_sync_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.runner.agent.PydanticAgent"):
        agent = Agent(config=AgentConfig(instructions="x"))

    fake = mock.Mock()
    fake.run_sync.return_value = SimpleNamespace(output={"ok": True})
    agent._pydantic_agent = fake

    result = agent.run_sync({"a": 1})

    assert result.output == {"ok": True}
    fake.run_sync.assert_called_once_with('{"a": 1}')


def test_agent_run_async_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.runner.agent.PydanticAgent"):
        agent = Agent(config=AgentConfig(instructions="x"))

    class FakeAsync:
        async def run(self, payload):
            assert payload == '{"b": 2}'
            return SimpleNamespace(output={"ok": True})

    agent._pydantic_agent = FakeAsync()

    result = asyncio.run(agent.run({"b": 2}))

    assert result.output == {"ok": True}


def test_agent_config_default_execution_backend() -> None:
    config = AgentConfig(instructions="test")
    assert config.execution_backend == "pydantic_ai"


@pytest.mark.parametrize("backend", ["pi_worker", "invalid"])
def test_agent_config_rejects_unsupported_backend(backend: str) -> None:
    with pytest.raises(ValueError, match="execution_backend"):
        AgentConfig(instructions="test", execution_backend=backend)


def test_json_safe_value_normalizes_nested_values() -> None:
    value = _json_safe_value(
        {
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "at": datetime(2026, 5, 1, 12, 0, 0),
            "enum": DemoEnum.VALUE,
            "data": DemoData(value=3),
            "items": (DemoData(value=4),),
        }
    )

    assert value == {
        "id": "12345678-1234-5678-1234-567812345678",
        "at": "2026-05-01T12:00:00",
        "enum": "value",
        "data": {"value": 3},
        "items": [{"value": 4}],
    }
