from __future__ import annotations

import pytest

from agents.agent import AgentConfig
from agents.agent_config_catalog import AgentConfigCatalog


def test_register_and_resolve_agent_config() -> None:
    AgentConfigCatalog.register_agent_config(
        "default",
        lambda: AgentConfig(instructions="hello"),
    )

    resolved = AgentConfigCatalog.resolve_agent_config("default")

    assert isinstance(resolved, AgentConfig)
    assert resolved.instructions == "hello"


def test_register_rejects_duplicate_key() -> None:
    AgentConfigCatalog.register_agent_config(
        "duplicate",
        lambda: AgentConfig(instructions="first"),
    )

    with pytest.raises(ValueError, match="Duplicate agent config key 'duplicate'."):
        AgentConfigCatalog.register_agent_config(
            "duplicate",
            lambda: AgentConfig(instructions="second"),
        )


def test_resolve_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown agent config key 'missing'."):
        AgentConfigCatalog.resolve_agent_config("missing")


def test_resolve_rejects_invalid_resolver_output() -> None:
    AgentConfigCatalog.register_agent_config("bad", lambda: "oops")

    with pytest.raises(TypeError, match="expected AgentConfig"):
        AgentConfigCatalog.resolve_agent_config("bad")


def test_validate_registry_iterates_all_resolvers() -> None:
    AgentConfigCatalog.register_agent_config("a", lambda: AgentConfig(instructions="A"))
    AgentConfigCatalog.register_agent_config("b", lambda: AgentConfig(instructions="B"))

    AgentConfigCatalog.validate_registry()

    assert AgentConfigCatalog.list_agent_config_keys() == ["a", "b"]
