"""Default catalog for public agent definitions."""

from collections.abc import Callable

from agents.core.inference.definition_catalog import DefinitionCatalog
from agents.inferences.agents import AgentDefinition


class AgentDefinitionCatalog(DefinitionCatalog[AgentDefinition]):
    """Store reusable agent definitions in this catalog's own registry."""

    definition_type = AgentDefinition
    definition_label = "agent definition"

    @classmethod
    def register_agent_definition(
        cls,
        key: str,
        resolver: Callable[[], AgentDefinition],
    ) -> None:
        """Register an agent definition factory under a stable key."""

        cls.register(key, resolver)

    @classmethod
    def resolve_agent_definition(cls, key: str) -> AgentDefinition:
        """Build the agent definition registered under ``key``."""

        return cls.resolve(key)

    @classmethod
    def list_agent_definition_keys(cls) -> list[str]:
        """Return registered keys in sorted order."""

        return cls.list_keys()


__all__ = ("AgentDefinitionCatalog",)
