"""Shared runner delegation supports both inference adapter contracts."""

import asyncio
from types import SimpleNamespace

import pytest

from agents.core.inference import DefinitionCatalog, InferenceRunner
from agents.core.inference.adapters import AgentAdapter, ChoiceAdapter
from agents.inferences.agents import AgentDefinition
from agents.inferences.choices import ChoiceDefinition


def test_custom_domain_definitions_bind_independent_catalogs():
    class CustomAgent(AgentDefinition):
        @classmethod
        def _get_catalog(cls):
            return Agents

    class CustomChoice(ChoiceDefinition):
        @classmethod
        def _get_catalog(cls):
            return Choices

    class Agents(DefinitionCatalog[CustomAgent]):
        definition_type = CustomAgent
        definition_label = "custom agent"

    class Choices(DefinitionCatalog[CustomChoice]):
        definition_type = CustomChoice
        definition_label = "custom choice"

    agent = CustomAgent(instructions="Answer")
    choice = CustomChoice("Which?", "Best fit", dict, dict, candidates={"one": 1})
    agent.register("shared")
    choice.register("shared")

    assert Agents.resolve("shared") is agent
    assert Choices.resolve("shared") is choice
    Agents.register("wrong", lambda: choice)
    with pytest.raises(TypeError, match="expected CustomAgent"):
        Agents.resolve("wrong")
    assert Choices.list_keys() == ["shared"]


@pytest.mark.parametrize("adapter_base", [AgentAdapter, ChoiceAdapter])
def test_shared_runner_preserves_payload_result_and_errors(adapter_base):
    result = SimpleNamespace(output={"answer": "one"})
    seen = []

    class Adapter(adapter_base):
        name = "custom"

        def run_sync(self, input_payload=None):
            seen.append(input_payload)
            if input_payload == "fail":
                raise ValueError("inference failed")
            return result

        async def run(self, input_payload=None):
            return self.run_sync(input_payload)

    adapter = Adapter()
    runner = InferenceRunner(adapter)
    payload = {"input": "question"}
    assert runner.adapter is adapter
    assert runner.name == "custom"
    assert runner.run_sync(payload) is result
    assert asyncio.run(runner.run(payload)) is result
    assert seen[0] is payload and seen[1] is payload
    with pytest.raises(ValueError, match="inference failed"):
        runner.run_sync("fail")
    with pytest.raises(ValueError, match="inference failed"):
        asyncio.run(runner.run("fail"))
