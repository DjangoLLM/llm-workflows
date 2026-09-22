"""Shared factory behavior and isolation between definition catalogs."""

import pytest

from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog
from agents.catalog.choice_definition_catalog import ChoiceDefinitionCatalog
from agents.inferences.agents import AgentDefinition
from agents.inferences.choices import ChoiceDefinition


def test_agent_and_choice_catalogs_can_use_the_same_key():
    agent = AgentDefinition(instructions="Choose a project")
    choice = ChoiceDefinition(
        question="Which project?", criteria="Closest topic",
        input_type=dict, result_type=dict, candidates={"project": "Project"},
    )
    agent.register("shared")
    choice.register("shared")

    assert AgentDefinitionCatalog.resolve_agent_definition("shared") is agent
    assert ChoiceDefinitionCatalog.resolve_choice_definition("shared") is choice

    AgentDefinitionCatalog._resolvers.clear()
    assert ChoiceDefinitionCatalog.resolve_choice_definition("shared") is choice


def test_catalog_subclasses_have_independent_storage():
    class LocalAgents(AgentDefinitionCatalog):
        pass

    AgentDefinitionCatalog.register("shared", lambda: AgentDefinition(instructions="parent"))
    assert LocalAgents.list_keys() == []
    LocalAgents.register("shared", lambda: AgentDefinition(instructions="child"))

    assert LocalAgents.resolve("shared").instructions == "child"
    assert AgentDefinitionCatalog.resolve("shared").instructions == "parent"


@pytest.mark.parametrize("catalog", [AgentDefinitionCatalog, ChoiceDefinitionCatalog])
def test_empty_keys_are_rejected(catalog):
    with pytest.raises(ValueError, match="key cannot be empty"):
        catalog.register("", lambda: None)
    assert catalog.list_keys() == []


def test_factory_is_called_for_each_resolution_and_validation():
    created = []

    def factory():
        definition = AgentDefinition(instructions="fresh")
        created.append(definition)
        return definition

    AgentDefinitionCatalog.register("fresh", factory)
    assert created == []
    first = AgentDefinitionCatalog.resolve("fresh")
    second = AgentDefinitionCatalog.resolve("fresh")
    AgentDefinitionCatalog.validate_registry()

    assert first is not second
    assert len(created) == 3
