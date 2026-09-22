"""
Centralized AgentDefinition registration entrypoint.
"""

from __future__ import annotations

from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog

_REGISTERED = False


def register_all_agent_definitions() -> None:
    """
    Register AgentDefinition resolvers exactly once.

    :return: None.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    # Placeholder for future AgentDefinition registrations.

    _REGISTERED = True
