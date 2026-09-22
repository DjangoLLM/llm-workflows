from __future__ import annotations

import pytest

from agents.inferences.agents import AgentDefinition
from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog


def test_register_and_resolve_agent_definition() -> None:
    AgentDefinitionCatalog.register_agent_definition(
        "default",
        lambda: AgentDefinition(instructions="hello"),
    )

    resolved = AgentDefinitionCatalog.resolve_agent_definition("default")

    assert isinstance(resolved, AgentDefinition)
    assert resolved.instructions == "hello"


def test_agent_definition_registers_itself() -> None:
    definition = AgentDefinition(instructions="hello")

    definition.register("default")

    assert AgentDefinitionCatalog.resolve_agent_definition("default") is definition


def test_register_rejects_duplicate_key() -> None:
    AgentDefinitionCatalog.register_agent_definition(
        "duplicate",
        lambda: AgentDefinition(instructions="first"),
    )

    with pytest.raises(ValueError, match="Duplicate agent definition key 'duplicate'."):
        AgentDefinitionCatalog.register_agent_definition(
            "duplicate",
            lambda: AgentDefinition(instructions="second"),
        )


def test_resolve_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown agent definition key 'missing'."):
        AgentDefinitionCatalog.resolve_agent_definition("missing")


def test_resolve_rejects_invalid_resolver_output() -> None:
    AgentDefinitionCatalog.register_agent_definition("bad", lambda: "oops")

    with pytest.raises(TypeError, match="expected AgentDefinition"):
        AgentDefinitionCatalog.resolve_agent_definition("bad")


def test_validate_registry_iterates_all_resolvers() -> None:
    AgentDefinitionCatalog.register_agent_definition("a", lambda: AgentDefinition(instructions="A"))
    AgentDefinitionCatalog.register_agent_definition("b", lambda: AgentDefinition(instructions="B"))

    AgentDefinitionCatalog.validate_registry()

    assert AgentDefinitionCatalog.list_agent_definition_keys() == ["a", "b"]
