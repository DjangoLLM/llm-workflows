"""
Central registry for named AgentConfig resolver functions.
"""

from __future__ import annotations

from typing import Callable, Dict

from agents.core.agent import AgentConfig


class AgentConfigCatalog:
    """
    Registry for named AgentConfig resolver functions.

    This catalog supports centralized registration and lookup
    of reusable agent configuration factories.
    """

    _resolvers: Dict[str, Callable[[], AgentConfig]] = {}

    @classmethod
    def register_agent_config(cls, key: str, resolver: Callable[[], AgentConfig]) -> None:
        """
        Register an AgentConfig resolver.

        :param key: Stable unique key for resolver lookup.
        :param resolver: Callable returning a valid AgentConfig.
        :return: None.
        :raises ValueError: If key is missing or already registered.
        """
        if not key:
            raise ValueError("Agent config key cannot be empty.")

        if key in cls._resolvers:
            raise ValueError(f"Duplicate agent config key '{key}'.")

        cls._resolvers[key] = resolver

    @classmethod
    def resolve_agent_config(cls, key: str) -> AgentConfig:
        """
        Resolve an AgentConfig from a named resolver.

        :param key: Registered resolver key.
        :return: Resolved AgentConfig instance.
        :raises ValueError: If key is unknown.
        :raises TypeError: If resolver returns invalid output.
        """
        if key not in cls._resolvers:
            raise ValueError(f"Unknown agent config key '{key}'.")

        config = cls._resolvers[key]()
        if not isinstance(config, AgentConfig):
            raise TypeError(
                f"Resolver for '{key}' returned {type(config).__name__}, expected AgentConfig."
            )
        return config

    @classmethod
    def list_agent_config_keys(cls) -> list[str]:
        """
        Return registered agent config keys.

        :return: Sorted resolver keys.
        """
        return sorted(cls._resolvers.keys())

    @classmethod
    def validate_registry(cls) -> None:
        """
        Validate all registered resolvers.

        :return: None.
        :raises TypeError: If any resolver output is invalid.
        """
        for key in cls.list_agent_config_keys():
            cls.resolve_agent_config(key)
