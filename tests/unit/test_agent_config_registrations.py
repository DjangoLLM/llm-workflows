from __future__ import annotations

from agents.agent_config_catalog import AgentConfigCatalog
from agents.agent_config_registrations import register_all_agent_configs


def test_register_all_agent_configs_is_idempotent() -> None:
    register_all_agent_configs()
    register_all_agent_configs()

    keys = AgentConfigCatalog.list_agent_config_keys()
    assert keys == []
