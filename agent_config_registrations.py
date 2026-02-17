"""
Centralized AgentConfig registration entrypoint.
"""

from __future__ import annotations

from agents.agent import AgentConfig
from agents.agent_config_catalog import AgentConfigCatalog

_REGISTERED = False


def _default_transcript_agent_config() -> AgentConfig:
    """
    Provide a reusable baseline AgentConfig.

    :return: AgentConfig baseline for transcript-oriented tasks.
    """
    return AgentConfig(
        instructions="Process transcript content with concise, structured outputs.",
    )


def register_all_agent_configs() -> None:
    """
    Register AgentConfig resolvers exactly once.

    :return: None.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    # Register baseline resolver for reusable projects.

    AgentConfigCatalog.register_agent_config(
        key="default_transcript_agent",
        resolver=_default_transcript_agent_config,
    )

    _REGISTERED = True
