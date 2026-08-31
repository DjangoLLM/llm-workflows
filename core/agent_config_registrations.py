"""
Centralized AgentConfig registration entrypoint.
"""

from __future__ import annotations

from agents.core.agent_config_catalog import AgentConfigCatalog

_REGISTERED = False


def register_all_agent_configs() -> None:
    """
    Register AgentConfig resolvers exactly once.

    :return: None.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    # Placeholder for future AgentConfig registrations.

    _REGISTERED = True
