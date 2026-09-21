from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest
from django.conf import settings as django_settings

from agents.core.agent import Agent, AgentConfig


def _patch_openai_model_construction(monkeypatch) -> None:
    monkeypatch.setattr("agents.core.agent.OpenAIResponsesModel", lambda model: f"model:{model}")
    monkeypatch.setattr(
        "agents.core.agent.OpenAIResponsesModelSettings",
        lambda **kwargs: {"settings": kwargs},
    )


def test_agent_requires_config_or_default(monkeypatch) -> None:
    monkeypatch.setattr(django_settings, "DEFAULT_AGENT_CONFIG", None, raising=False)

    with pytest.raises(ValueError, match="DEFAULT_AGENT_CONFIG"):
        Agent()


def test_agent_uses_explicit_config_with_string_model(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent") as pydantic_agent:
        Agent(config=AgentConfig(instructions="test", model="gpt-5-mini"))

    pydantic_agent.assert_called_once_with(
        model="model:gpt-5-mini",
        model_settings={"settings": {"openai_reasoning_effort": "none"}},
        instructions="test",
    )


def test_agent_builds_config_from_kwargs(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent") as pydantic_agent:
        Agent(instructions="from kwargs", model="gpt-5-mini")

    pydantic_agent.assert_called_once_with(
        model="model:gpt-5-mini",
        model_settings={"settings": {"openai_reasoning_effort": "none"}},
        instructions="from kwargs",
    )


def test_agent_uses_default_settings_config(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    default_config = AgentConfig(
        instructions="from defaults",
        model="configured-model",
    )
    monkeypatch.setattr(
        django_settings,
        "DEFAULT_AGENT_CONFIG",
        default_config,
        raising=False,
    )

    with mock.patch("agents.core.agent.PydanticAgent") as pydantic_agent:
        agent = Agent()

    assert agent.config is default_config
    pydantic_agent.assert_called_once_with(
        model="model:configured-model",
        model_settings={"settings": {"openai_reasoning_effort": "none"}},
        instructions="from defaults",
    )


def test_agent_defaults_to_gpt_5_mini(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)

    with mock.patch("agents.core.agent.PydanticAgent") as pydantic_agent:
        Agent(config=AgentConfig(instructions="test"))

    pydantic_agent.assert_called_once_with(
        model="model:gpt-5-mini",
        model_settings={"settings": {"openai_reasoning_effort": "none"}},
        instructions="test",
    )


def test_agent_preserves_direct_model_configuration(monkeypatch) -> None:
    supplied_model = object()
    supplied_settings = object()

    def explicit_tool() -> str:
        return "explicit"

    def registered_tool() -> str:
        return "registered"

    monkeypatch.setattr(
        "agents.core.tools.default_registry.resolve_toolset",
        lambda name: [registered_tool] if name == "registered" else [],
    )
    monkeypatch.setattr(
        "agents.core.tools.pydantic_ai_adapter.build_pydantic_ai_tool",
        lambda tool: tool,
    )

    with mock.patch("agents.core.agent.PydanticAgent") as pydantic_agent:
        Agent(
            config=AgentConfig(
                instructions="configured",
                model=supplied_model,
                settings=supplied_settings,
                result_type=dict[str, str],
                tools=[explicit_tool],
                toolsets=["registered"],
                extra_kwargs={"retries": 4},
            )
        )

    pydantic_agent.assert_called_once_with(
        model=supplied_model,
        model_settings=supplied_settings,
        instructions="configured",
        output_type=dict[str, str],
        tools=[explicit_tool, registered_tool],
        retries=4,
    )


def test_agent_run_sync_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent"):
        agent = Agent(config=AgentConfig(instructions="x"))

    fake = mock.Mock()
    fake.run_sync.return_value = SimpleNamespace(output={"ok": True})
    agent._pydantic_agent = fake

    result = agent.run_sync({"a": 1})

    assert result.output == {"ok": True}
    fake.run_sync.assert_called_once_with('{"a": 1}')


def test_agent_run_async_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent"):
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
    with pytest.raises(
        ValueError,
        match=rf"execution_backend must be 'pydantic_ai' or 'jev'; got '{backend}'",
    ):
        AgentConfig(instructions="test", execution_backend=backend)


def test_agent_kwargs_reject_backend_before_model_or_registry_resolution(monkeypatch) -> None:
    construct_model = mock.Mock(side_effect=AssertionError("model constructed"))
    resolve_toolset = mock.Mock(side_effect=AssertionError("registry resolved"))
    monkeypatch.setattr("agents.core.agent.OpenAIResponsesModel", construct_model)
    monkeypatch.setattr(
        "agents.core.tools.default_registry.resolve_toolset",
        resolve_toolset,
    )

    with pytest.raises(
        ValueError,
        match="execution_backend must be 'pydantic_ai' or 'jev'; got 'pi_worker'",
    ):
        Agent(
            instructions="test",
            execution_backend="pi_worker",
            model="never-constructed",
            toolsets=["never-resolved"],
        )

    construct_model.assert_not_called()
    resolve_toolset.assert_not_called()
