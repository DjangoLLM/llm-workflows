from __future__ import annotations

from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog
from agents.runner.agent_definition_registrations import register_all_agent_definitions


def test_register_all_agent_definitions_is_idempotent() -> None:
    register_all_agent_definitions()
    register_all_agent_definitions()

    keys = AgentDefinitionCatalog.list_agent_definition_keys()
    assert keys == []
