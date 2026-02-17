from __future__ import annotations

from agents.agent_config_catalog import AgentConfigCatalog
from agents.agent_config_registrations import register_all_agent_configs


def test_register_all_agent_configs_is_idempotent() -> None:
    register_all_agent_configs()
    register_all_agent_configs()

    keys = AgentConfigCatalog.list_agent_config_keys()
    assert keys == ["default_transcript_agent"]


def test_registered_default_config_resolves() -> None:
    register_all_agent_configs()

    config = AgentConfigCatalog.resolve_agent_config("default_transcript_agent")

    assert "transcript" in config.instructions.lower()
